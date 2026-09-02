#!/usr/bin/env python3
"""Remote work process: independent of the monitor, writes a harvestable result.

Progress is written to a sidecar so a kill mid-run cannot be mistaken for a
complete result. The harvest artifact appears only via os.replace at the end.
Then this process appends work-completed to the durable ledger itself.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from ledger import append_event  # noqa: E402


def atomic_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", required=True)
    p.add_argument("--nonce", required=True)
    p.add_argument("--duration-s", type=float, default=0.8)
    args = p.parse_args()
    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    pid = os.getpid()
    (run_dir / "work.pid").write_text(str(pid), encoding="utf-8")
    append_event(
        run_dir,
        {
            "event": "work-started",
            "actor": "worker",
            "pid": pid,
            "nonce": args.nonce,
        },
    )
    atomic_write(
        run_dir / "work.ready",
        {"pid": pid, "nonce": args.nonce, "ready": True},
    )
    steps = max(8, int(args.duration_s / 0.05))
    slice_s = args.duration_s / steps
    for i in range(steps):
        atomic_write(
            run_dir / "work.progress",
            {"pid": pid, "step": i + 1, "of": steps, "nonce": args.nonce},
        )
        time.sleep(slice_s)
    result = {
        "nonce": args.nonce,
        "pid": pid,
        "status": "complete",
        "payload": f"remote-work-result:{args.nonce}",
        "steps": steps,
    }
    atomic_write(run_dir / "result.json", result)
    append_event(
        run_dir,
        {
            "event": "work-completed",
            "actor": "worker",
            "pid": pid,
            "nonce": args.nonce,
            "result_path": "result.json",
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
