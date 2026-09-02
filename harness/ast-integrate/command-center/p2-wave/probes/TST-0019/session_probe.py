#!/usr/bin/env python3
"""Process-table session probe with an explicit self-match guard.

The measured failure is a Win32_Process (here: /proc cmdline) scan whose
pattern also appears in the probing process's own command line. Unguarded,
the probe reports itself as an ACTIVE session; the tell is start-key equality
with the probe's own start (CreationDate analog).

The guard excludes the probing process by PID and by start-key equality.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MARKER = "TST-0019-SESSION-MARKER"
PROC = Path("/proc")


def boot_time_unix() -> int | None:
    try:
        for line in Path("/proc/stat").read_text(encoding="utf-8").splitlines():
            if line.startswith("btime "):
                return int(line.split()[1])
    except (OSError, ValueError, IndexError):
        return None
    return None


def clk_tck() -> int:
    try:
        return int(os.sysconf("SC_CLK_TCK"))
    except (OSError, ValueError, TypeError):
        return 100


def read_cmdline(pid: int) -> str:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return ""
    return raw.replace(b"\x00", b" ").decode("utf-8", "replace").strip()


def read_start_ticks(pid: int) -> int | None:
    try:
        text = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except OSError:
        return None
    rparen = text.rfind(")")
    if rparen < 0:
        return None
    fields = text[rparen + 1 :].split()
    if len(fields) < 20:
        return None
    try:
        return int(fields[19])
    except ValueError:
        return None


def ticks_to_cim(ticks: int | None) -> str:
    if ticks is None:
        return ""
    btime = boot_time_unix()
    if btime is None:
        return str(ticks)
    hz = clk_tck() or 100
    unix = btime + (ticks / float(hz))
    dt = datetime.fromtimestamp(unix, tz=timezone.utc)
    return dt.strftime("%Y%m%d%H%M%S.%f")[:-3] + "-000"


def is_self(proc: dict[str, Any], probe_pid: int, probe_start_key: str) -> bool:
    if int(proc.get("pid") or -1) == int(probe_pid):
        return True
    key = str(proc.get("start_key") or "")
    if probe_start_key and key and key == str(probe_start_key):
        return True
    return False


def list_processes() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        entries = list(PROC.iterdir())
    except OSError:
        return rows
    for entry in entries:
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        cmdline = read_cmdline(pid)
        ticks = read_start_ticks(pid)
        start_key = str(ticks) if ticks is not None else ""
        rows.append(
            {
                "pid": pid,
                "cmdline": cmdline,
                "start_key": start_key,
                "start_ticks": ticks,
                "creation_date": ticks_to_cim(ticks),
            }
        )
    return rows


def scan_snapshot(snapshot: dict[str, Any], *, guarded: bool) -> dict[str, Any]:
    pattern = str(snapshot.get("pattern") or MARKER)
    probe_pid = int(snapshot["probe_pid"])
    probe_start_key = str(snapshot.get("probe_start_key") or "")
    excluded: list[dict[str, Any]] = []
    matches: list[dict[str, Any]] = []
    for proc in snapshot.get("processes") or []:
        cmdline = str(proc.get("cmdline") or "")
        if pattern not in cmdline:
            continue
        rec = {
            "pid": int(proc["pid"]),
            "cmdline": cmdline,
            "start_key": str(proc.get("start_key") or proc.get("creation_date") or ""),
            "creation_date": str(proc.get("creation_date") or proc.get("start_key") or ""),
        }
        if guarded and is_self(rec, probe_pid, probe_start_key):
            rec["excluded_reason"] = (
                "own-pid" if rec["pid"] == probe_pid else "start-key-equality"
            )
            excluded.append(rec)
            continue
        matches.append(rec)
    self_hits = [m for m in matches if is_self(m, probe_pid, probe_start_key)]
    return {
        "pattern": pattern,
        "probe_pid": probe_pid,
        "probe_start_key": probe_start_key,
        "guarded": bool(guarded),
        "matches": matches,
        "excluded": excluded,
        "self_match": bool(self_hits),
        "self_pids": [m["pid"] for m in self_hits],
        "match_pids": [m["pid"] for m in matches],
    }


def scan_live(pattern: str = MARKER, *, guarded: bool) -> dict[str, Any]:
    probe_pid = os.getpid()
    ticks = read_start_ticks(probe_pid)
    probe_start_key = str(ticks) if ticks is not None else ""
    snapshot = {
        "pattern": pattern,
        "probe_pid": probe_pid,
        "probe_start_key": probe_start_key,
        "processes": list_processes(),
    }
    out = scan_snapshot(snapshot, guarded=guarded)
    out["probe_creation_date"] = ticks_to_cim(ticks)
    out["substrate"] = "linux-/proc"
    return out


def load_fixture(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TST-0019 session probe")
    parser.add_argument("cmd", choices=["scan"])
    parser.add_argument("--pattern", default=MARKER)
    parser.add_argument("--mode", choices=["unguarded", "guarded"], required=True)
    parser.add_argument("--fixture", default="")
    args = parser.parse_args(argv)
    guarded = args.mode == "guarded"
    if args.fixture:
        snap = load_fixture(Path(args.fixture))
        doc = scan_snapshot(snap, guarded=guarded)
        doc["substrate"] = "fixture"
    else:
        doc = scan_live(args.pattern, guarded=guarded)
    sys.stdout.write(json.dumps(doc, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
