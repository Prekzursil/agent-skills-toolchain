"""Commit-charge vs working-set counters.

Windows maps: Commit Charge, Available Commit, Working Set, Event 2004.
This Linux worktree maps:
  commit_charge     <- /proc/meminfo Committed_AS
  commit_limit      <- /proc/meminfo CommitLimit
  available_commit  <- CommitLimit - Committed_AS
  working_set       <- /proc/meminfo Active  (Task Manager analog: resident)
  ram_total         <- /proc/meminfo MemTotal
A probe that reads MemAvailable or Active is silent in the commit-exhaustion
state that actually freezes process creation.
"""
from __future__ import annotations

import mmap
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

MEMINFO_PATH = Path("/proc/meminfo")
SELF_STATUS = Path("/proc/self/status")
OVERCOMMIT_PATH = Path("/proc/sys/vm/overcommit_memory")
OVERCOMMIT_RATIO_PATH = Path("/proc/sys/vm/overcommit_ratio")

_MEMINFO_LINE = re.compile(r"^([A-Za-z0-9_()]+):\s+(\d+)(?:\s+kB)?\s*$")
_STATUS_LINE = re.compile(r"^([A-Za-z0-9_()]+):\s+(\d+)\s+kB\s*$")

HOST_ABORT_RATIO = 0.70
MMAP_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True)
class Sample:
    step: int
    ts_ns: int
    commit_charge: int
    available_commit: int
    commit_limit: int
    working_set: int
    ram_total: int
    n_processes: int
    event: str

    def to_dict(self) -> dict:
        return asdict(self)

    def commit_ratio(self) -> float:
        if self.commit_limit <= 0:
            return 1.0
        return self.commit_charge / self.commit_limit

    def working_set_ratio(self) -> float:
        if self.ram_total <= 0:
            return 1.0
        return self.working_set / self.ram_total


def parse_meminfo(text: str) -> dict[str, int]:
    """Parse /proc/meminfo text. Values are kilobytes when the line has kB."""
    out: dict[str, int] = {}
    for line in text.splitlines():
        m = _MEMINFO_LINE.match(line)
        if m:
            out[m.group(1)] = int(m.group(2))
    return out


def parse_status(text: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for line in text.splitlines():
        m = _STATUS_LINE.match(line)
        if m:
            out[m.group(1)] = int(m.group(2))
    return out


def _kb(fields: Mapping[str, int], name: str) -> int:
    if name not in fields:
        raise KeyError(f"missing meminfo field {name}")
    return int(fields[name]) * 1024


def snapshot_from_meminfo(text: str, *, step: int = 0, ts_ns: int = 0) -> Sample:
    fields = parse_meminfo(text)
    charge = _kb(fields, "Committed_AS")
    limit = _kb(fields, "CommitLimit")
    ram = _kb(fields, "MemTotal")
    # Active is the resident-set analog. Must NOT be used as commit charge.
    ws = _kb(fields, "Active")
    return Sample(
        step=step,
        ts_ns=ts_ns,
        commit_charge=charge,
        available_commit=limit - charge,
        commit_limit=limit,
        working_set=ws,
        ram_total=ram,
        n_processes=0,
        event="host-meminfo",
    )


def live_host_snapshot() -> Sample:
    return snapshot_from_meminfo(MEMINFO_PATH.read_text(encoding="utf-8"))


def self_status_bytes() -> dict[str, int]:
    fields = parse_status(SELF_STATUS.read_text(encoding="utf-8"))
    return {
        "VmRSS_bytes": int(fields.get("VmRSS", 0)) * 1024,
        "VmSize_bytes": int(fields.get("VmSize", 0)) * 1024,
        "RssAnon_bytes": int(fields.get("RssAnon", 0)) * 1024,
    }


def host_meta() -> dict:
    overcommit = "unknown"
    ratio = "unknown"
    try:
        overcommit = OVERCOMMIT_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    try:
        ratio = OVERCOMMIT_RATIO_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    snap = live_host_snapshot()
    return {
        "os": "linux",
        "commit_probe_source": "/proc/meminfo:Committed_AS",
        "available_commit_source": "/proc/meminfo:CommitLimit-Committed_AS",
        "working_set_source": "/proc/meminfo:Active",
        "overcommit_memory": overcommit,
        "overcommit_ratio": ratio,
        "commit_charge_bytes": snap.commit_charge,
        "available_commit_bytes": snap.available_commit,
        "commit_limit_bytes": snap.commit_limit,
        "working_set_bytes": snap.working_set,
        "ram_total_bytes": snap.ram_total,
        "commit_ratio": round(snap.commit_ratio(), 6),
        "working_set_ratio": round(snap.working_set_ratio(), 6),
        "windows_event_2004": (
            "not-emitted-on-linux; process-creation failure is simulated as "
            "spawn rejection when commit_charge would exceed commit_limit"
        ),
        "note": (
            "SwapTotal may be 0, so CommitLimit is RAM*overcommit_ratio/100. "
            "Task Manager working-set analog is Active/VmRSS; those counters "
            "stay low while Committed_AS accounts untouched anonymous maps."
        ),
    }


def demonstrate_commit_rss_divergence(
    nbytes: int = MMAP_BYTES,
) -> dict:
    """Untouched anonymous mmap: commit charge moves, RSS does not.

    Aborts the live mapping if the host is already near its commit ceiling.
    Never drives the box toward freeze.
    """
    before_host = live_host_snapshot()
    ratio = before_host.commit_ratio()
    if ratio > HOST_ABORT_RATIO:
        return {
            "skipped": True,
            "reason": "host-commit-ratio-above-abort",
            "ratio": ratio,
            "abort_ratio": HOST_ABORT_RATIO,
        }
    if before_host.available_commit < nbytes * 4:
        return {
            "skipped": True,
            "reason": "insufficient-available-commit",
            "available_commit": before_host.available_commit,
            "requested": nbytes,
        }
    before_self = self_status_bytes()
    buf = mmap.mmap(-1, nbytes)
    try:
        after_host = live_host_snapshot()
        after_self = self_status_bytes()
    finally:
        buf.close()
    d_commit = after_host.commit_charge - before_host.commit_charge
    d_ws = after_host.working_set - before_host.working_set
    d_rss = after_self["VmRSS_bytes"] - before_self["VmRSS_bytes"]
    d_vmsize = after_self["VmSize_bytes"] - before_self["VmSize_bytes"]
    return {
        "skipped": False,
        "nbytes": nbytes,
        "d_commit_charge_bytes": d_commit,
        "d_working_set_bytes": d_ws,
        "d_rss_bytes": d_rss,
        "d_vmsize_bytes": d_vmsize,
        "commit_moved": d_commit >= nbytes // 2 or d_vmsize >= nbytes - 1024 * 1024,
        "rss_silent": d_rss < 2 * 1024 * 1024,
        "before_commit_charge": before_host.commit_charge,
        "after_commit_charge": after_host.commit_charge,
        "before_working_set": before_host.working_set,
        "after_working_set": after_host.working_set,
    }
