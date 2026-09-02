#!/usr/bin/env python3
"""Heartbeat monitor. Observes work pid liveness; does not own the work.

Death of this process is recorded by the supervisor as monitor-died. This
process never writes monitor-died itself, so a SIGKILL cannot be confused with
a self-reported shutdown. Liveness is os.kill(pid, 0), never file mtime.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from ledger import append_event  # noqa: E402


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", required=True)
    p.add_argument("--work-pid", type=int, required=True)
    p.add_argument("--interval-s", type=float, default=0.04)
    args = p.parse_args()
    run_dir = Path(args.run_dir)
    pid = os.getpid()
    (run_dir / "monitor.pid").write_text(str(pid), encoding="utf-8")
    append_event(
        run_dir,
        {
            "event": "monitor-started",
            "actor": "monitor",
            "pid": pid,
            "work_pid": args.work_pid,
        },
    )
    seq = 0
    while True:
        seq += 1
        alive = pid_alive(args.work_pid)
        append_event(
            run_dir,
            {
                "event": "monitor-heartbeat",
                "actor": "monitor",
                "pid": pid,
                "seq_hb": seq,
                "work_pid": args.work_pid,
                "work_pid_alive": alive,
                "signal_source": "os.kill(pid,0)",
            },
        )
        time.sleep(args.interval_s)
        # Keep heartbeating even if work exits: silence is the monitor's death,
        # not the work's. The supervisor records work-died / work-completed.


if __name__ == "__main__":
    raise SystemExit(main())
