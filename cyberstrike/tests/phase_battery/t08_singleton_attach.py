#!/usr/bin/env python3
"""T-8 singleton attach - duplicate-TUI detection via manifest liveness.

G-12=B CUT the lockfile singleton guard: duplicate TUI stacks are detected
via MANIFEST LIVENESS instead (fresh heartbeats from >1 distinct pid in the
session shards). Lockfiles lie (stale after crash); liveness is the signal.

Pre-manifest (now): the process table is OBSERVED read-only and recorded as
a SINGLE-SIGNAL informational hit - never a verdict (one probe is not
evidence). The verdict stays PENDING-OWNER until the Phase-3 manifest exists.
The running TUI (PID 19684 at battery-build time) is never touched, killed,
or signaled - observation only.

Post-manifest: counts distinct pids with a heartbeat newer than --window-min
(10 min default) across shards; >1 live pid = duplicate-stack hit.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from battery_common import (  # noqa: E402
    REPO, SUCCESS, FAILED, PENDING_OWNER,
    VerdictRecorder,
)

DATA = Path.home() / ".local" / "share" / "cyberstrike"
SHARD_DIR = DATA / "manifest" / "sessions"
WINDOW_MIN = 10


def observe_process_table(rec: VerdictRecorder) -> list[dict]:
    """Read-only observation. PowerShell Get-Process, no side effects."""
    cmd = ["powershell", "-NoProfile", "-Command",
           "Get-Process | Where-Object { $_.ProcessName -like '*cyberstrike*' } "
           "| Select-Object Id,ProcessName,StartTime "
           "| ConvertTo-Json -Compress"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                           encoding="utf-8", errors="replace")
        raw = (r.stdout or "").strip()
        procs = []
        if raw:
            parsed = json_loads_safe(raw)
            blobs = parsed if isinstance(parsed, list) else [parsed]
            procs = [{"pid": b.get("Id"), "name": b.get("ProcessName")}
                     for b in blobs if isinstance(b, dict)]
        for p in procs:
            rec.hit("T-8", "process_observation", single_signal=True, **p)
        return procs
    except Exception as e:  # observation failure is not a verdict
        rec.hit("T-8", "process_observation_error", error=str(e)[:200])
        return []


def json_loads_safe(s: str):
    import json
    try:
        return json.loads(s)
    except Exception:
        return {}


def manifest_liveness(rec: VerdictRecorder) -> dict | None:
    """Distinct pids with fresh heartbeats across shards; None if no manifest."""
    if not (SHARD_DIR.exists() and any(SHARD_DIR.glob("*.ndjson"))):
        return None
    import json
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=WINDOW_MIN)
    live_pids: dict[str, str] = {}
    for shard in SHARD_DIR.glob("*.ndjson"):
        try:
            lines = shard.read_text(encoding="utf-8",
                                    errors="replace").splitlines()
        except OSError:
            continue
        for line in reversed(lines):          # newest last in append-only shard
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts, pid = row.get("ts"), row.get("pid")
            if not (ts and pid):
                continue
            try:
                when = datetime.fromisoformat(ts)
            except ValueError:
                continue
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            if when >= cutoff:
                live_pids[str(pid)] = shard.stem
            break                              # newest row decides liveness
    for pid, sid in live_pids.items():
        rec.hit("T-8", "manifest_liveness", pid=pid, newest_shard=sid)
    return {"live_pids": sorted(live_pids), "count": len(live_pids)}


def run(rec: VerdictRecorder, opts: dict | None = None) -> str:
    liveness = manifest_liveness(rec)
    if liveness is None:
        procs = observe_process_table(rec)
        rec.record("T-8", PENDING_OWNER,
                   reason="NOT-RUNNABLE-needs-manifest (G-12=B: liveness "
                          "signal is the manifest; lockfile guard was cut)",
                   details={
                       "process_table_observed_read_only": procs,
                       "observation_is_single_signal": True,
                       "tui_note": "running TUI (e.g. PID 19684) observed "
                                   "only - never touched",
                       "shard_dir": str(SHARD_DIR),
                   },
                   anchors=[REPO / "plugin" / "manifest-writer.ts"])
        return PENDING_OWNER

    dup = liveness["count"] > 1
    rec.record("T-8", SUCCESS if not dup else FAILED,
               details={"live_pids": liveness["live_pids"],
                        "window_min": WINDOW_MIN,
                        "expected": "exactly 1 live TUI pid"},
               anchors=[SHARD_DIR],
               reason=None if not dup else
               f"duplicate TUI stacks: {liveness['live_pids']}")
    return SUCCESS if not dup else FAILED


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.parse_args()
    with VerdictRecorder(meta={"test": "T-8"}) as rec:
        status = run(rec)
        print(f"T-8 {status}")
        return 0 if status in (SUCCESS, PENDING_OWNER) else 1


if __name__ == "__main__":
    sys.exit(main())
