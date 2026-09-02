#!/usr/bin/env python3
"""Live Linux counters for BLD-0057.

Commit-charge analog is Committed_AS / CommitLimit from /proc/meminfo,
NOT RSS and NOT MemAvailable-derived RAM percent. Task Manager's working-set
view is the estate's known silent failure; the Linux equivalent silent view
is a RAM-percent reading while Committed_AS approaches CommitLimit.
"""
from __future__ import annotations

import os
import resource
import socket
from pathlib import Path
from typing import Any

PROC = Path("/proc")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def meminfo_bytes() -> dict[str, int]:
    out: dict[str, int] = {}
    for line in _read_text(PROC / "meminfo").splitlines():
        if ":" not in line:
            continue
        key, rest = line.split(":", 1)
        parts = rest.split()
        if not parts:
            continue
        try:
            val = int(parts[0])
        except ValueError:
            continue
        unit = parts[1].lower() if len(parts) > 1 else "kb"
        if unit == "kb":
            val *= 1024
        elif unit == "mb":
            val *= 1024 * 1024
        out[key] = val
    return out


def file_nr() -> tuple[int, int, int]:
    raw = _read_text(Path("/proc/sys/fs/file-nr")).split()
    allocated = int(raw[0])
    unused = int(raw[1]) if len(raw) > 1 else 0
    maximum = int(raw[2]) if len(raw) > 2 else allocated
    return allocated, unused, maximum


def process_count() -> int:
    n = 0
    with os.scandir("/proc") as it:
        for entry in it:
            name = entry.name
            if name.isdigit():
                n += 1
    return n


def sysctl_int(rel: str, default: int) -> int:
    path = Path("/proc/sys") / rel
    try:
        return int(_read_text(path).strip().split()[0])
    except (OSError, ValueError, IndexError):
        return default


def tagged_pids(marker: bytes) -> list[int]:
    found: list[int] = []
    with os.scandir("/proc") as it:
        for entry in it:
            if not entry.name.isdigit():
                continue
            env_path = Path("/proc") / entry.name / "environ"
            try:
                blob = env_path.read_bytes()
            except OSError:
                continue
            if marker in blob:
                found.append(int(entry.name))
    return found


def snapshot() -> dict[str, Any]:
    mi = meminfo_bytes()
    commit_limit = int(mi.get("CommitLimit") or 0)
    committed = int(mi.get("Committed_AS") or 0)
    mem_total = int(mi.get("MemTotal") or 0)
    mem_avail = int(mi.get("MemAvailable") or 0)
    swap_total = int(mi.get("SwapTotal") or 0)
    swap_free = int(mi.get("SwapFree") or 0)
    fd_alloc, fd_unused, fd_max = file_nr()
    nproc_soft, nproc_hard = resource.getrlimit(resource.RLIMIT_NPROC)
    ram_used_ratio = None
    if mem_total:
        ram_used_ratio = round((mem_total - mem_avail) / mem_total, 6)
    commit_ratio = round(committed / commit_limit, 6) if commit_limit else None
    uname = os.uname()
    return {
        "hostname": socket.gethostname(),
        "kernel": f"{uname.sysname} {uname.release}",
        "machine": uname.machine,
        "overcommit_memory": sysctl_int("vm/overcommit_memory", -1),
        "commit_limit_bytes": commit_limit,
        "committed_as_bytes": committed,
        "commit_ratio": commit_ratio,
        "mem_total_bytes": mem_total,
        "mem_available_bytes": mem_avail,
        "ram_used_ratio": ram_used_ratio,
        "swap_total_bytes": swap_total,
        "swap_free_bytes": swap_free,
        "process_count": process_count(),
        "pid_max": sysctl_int("kernel/pid_max", 32768),
        "threads_max": sysctl_int("kernel/threads-max", 32768),
        "nproc_soft": nproc_soft if nproc_soft != resource.RLIM_INFINITY else None,
        "nproc_hard": nproc_hard if nproc_hard != resource.RLIM_INFINITY else None,
        "fd_allocated": fd_alloc,
        "fd_unused": fd_unused,
        "fd_max": fd_max,
        "os_low_memory_event": "NOT-CHECKED",
        "os_low_memory_event_note": (
            "Linux has no Windows Event 2004 analog sampled here; "
            "psi/memory may exist but is not claimed as a firing event."
        ),
    }


def guard_view(snap: dict[str, Any]) -> dict[str, Any]:
    """Shape live snapshot fields the headroom guard consumes."""
    return {
        "commit_ratio": snap.get("commit_ratio"),
        "committed_as_bytes": snap.get("committed_as_bytes"),
        "commit_limit_bytes": snap.get("commit_limit_bytes"),
        "process_count": snap.get("process_count"),
        "fd_allocated": snap.get("fd_allocated"),
        "ram_used_ratio": snap.get("ram_used_ratio"),
    }


def mcp_like_census(limit: int = 4000) -> dict[str, Any]:
    hits: list[dict[str, str]] = []
    scanned = 0
    with os.scandir("/proc") as it:
        for entry in it:
            if not entry.name.isdigit():
                continue
            scanned += 1
            if scanned > limit:
                break
            cmd_path = Path("/proc") / entry.name / "cmdline"
            try:
                raw = cmd_path.read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")
            except OSError:
                continue
            low = raw.lower()
            if "mcp" in low or "/usr/bin/npx" in low:
                hits.append({"pid": entry.name, "cmd": raw[:180]})
    return {"scanned": scanned, "hits": hits, "count": len(hits)}
