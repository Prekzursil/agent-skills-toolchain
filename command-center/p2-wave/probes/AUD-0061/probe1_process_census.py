#!/usr/bin/env python3
"""AUD-0061 named probe 1: live MCP process census + per-session attribution.

Pure /proc introspection (no `ps` subprocess, so no transient forked process
can pollute the count). Records:
  - every process visible in /proc right now (raw_process_count)
  - this probe's OWN creation tick, and every process EXCLUDED because its
    creation tick exactly matches (self_excluded_count -- normally 1: this
    process itself)
  - the exec-daemon's declared --mcp-config (the configured MCP servers for
    THIS Cursor Cloud session)
  - how many LIVE processes on this host right now actually match one of
    those configured server definitions (mcp_live_process_count)
  - a session attribution: on a single-tenant Cursor Cloud pod there is
    exactly one exec-daemon and therefore exactly one detectable session;
    every matched MCP process is attributed to that session's bc_id.

Accepts an optional --self-tag argument purely so the paired control script
(control_self_exclusion.py) can inject a substring (e.g. containing "mcp")
into THIS probe's own argv, proving the starttime-based self-exclusion still
correctly drops the probe's own PID even when a naive substring matcher
would have flagged its command line as MCP-related.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _proc_census as C  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--self-tag",
        default="",
        help="opt-in argv marker for the self-exclusion control",
    )
    ap.add_argument(
        "--out", default="", help="write JSON to this path instead of stdout"
    )
    args = ap.parse_args(argv)

    started_wall = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    own_ticks = C.own_creation_ticks()
    own_pid = os.getpid()

    raw_rows = C.scan_raw()
    kept, excluded = C.apply_self_exclusion(raw_rows, own_ticks)

    self_row_in_raw = any(r["pid"] == own_pid for r in raw_rows)
    self_row_in_kept = any(r["pid"] == own_pid for r in kept)
    self_row_in_excluded = any(r["pid"] == own_pid for r in excluded)

    md = C.find_exec_daemon_mcp_config(kept) or C.find_exec_daemon_mcp_config(raw_rows)
    configured_servers = md["mcp_servers_config"] if md else {}

    live_matches = []
    for name, sdef in configured_servers.items():
        for row in kept:
            if C.server_match(row, name, sdef):
                live_matches.append(
                    {
                        "server_name": name,
                        "pid": row["pid"],
                        "ppid": row["ppid"],
                        "comm": row["comm"],
                        "cmdline_head": " ".join(row["cmdline"])[:200],
                        "vmrss_kb": row["vmrss_kb"],
                        "vmsize_kb": row["vmsize_kb"],
                        "starttime_ticks": row["starttime_ticks"],
                    }
                )

    session_id = md["bc_id"] if md and md.get("bc_id") else "unknown-single-session"
    sessions_detected = 1 if md else 0
    processes_by_session = {session_id: len(live_matches)} if md else {}

    ended_wall = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    doc = {
        "probe": "AUD-0061-probe1-process-census",
        "started_at": started_wall,
        "ended_at": ended_wall,
        "self_pid": own_pid,
        "self_starttime_ticks": own_ticks,
        "self_tag": args.self_tag,
        "hz": C.HZ,
        "boot_time_epoch": C.boot_time_epoch(),
        "raw_process_count": len(raw_rows),
        "self_excluded_count": len(excluded),
        "self_excluded_pids": [r["pid"] for r in excluded],
        "final_process_count": len(kept),
        "self_row_present_in_raw_scan": self_row_in_raw,
        "self_row_present_in_final_kept_set": self_row_in_kept,
        "self_row_present_in_excluded_set": self_row_in_excluded,
        "exec_daemon_found": md is not None,
        "exec_daemon_pid": md["exec_daemon_pid"] if md else None,
        "exec_daemon_vmrss_kb": md["exec_daemon_vmrss_kb"] if md else None,
        "exec_daemon_vmsize_kb": md["exec_daemon_vmsize_kb"] if md else None,
        "bc_id": md["bc_id"] if md else None,
        "mcp_configured_server_count": len(configured_servers),
        "mcp_configured_servers": {
            name: {"command": sdef.get("command"), "args": sdef.get("args", [])}
            for name, sdef in configured_servers.items()
        },
        "mcp_live_process_count": len(live_matches),
        "mcp_live_processes": live_matches,
        "sessions_detected": sessions_detected,
        "session_ids": [session_id] if md else [],
        "processes_by_session": processes_by_session,
        "ok": (not self_row_in_kept) and (self_row_in_excluded or not self_row_in_raw),
    }

    text = json.dumps(doc, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if doc["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
