#!/usr/bin/env python3
"""Fixture workers for CNF-0047 constructed states.

Modes:
  write-forever   <artifact>          — killed mid-write (no COMPLETE trailer)
  write-complete  <artifact>          — finishes and writes COMPLETE trailer
  idle-heartbeat  <artifact> <hb>     — pid stays alive, work file does not grow
  harvest-remote  <ledger> <artifact> <unit_id> [delay_s]
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

COMPLETE = b"\nCNF-0047-COMPLETE\n"


def _append_ledger(path: Path, rec: dict) -> None:
    rec = dict(rec)
    rec.setdefault("ts", time.time())
    rec.setdefault("pid", os.getpid())
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def write_forever(artifact: Path) -> None:
    artifact.parent.mkdir(parents=True, exist_ok=True)
    with artifact.open("wb") as fh:
        while True:
            fh.write(b"X" * 4096)
            fh.flush()
            os.fsync(fh.fileno())
            time.sleep(0.02)


def write_complete(artifact: Path) -> None:
    artifact.parent.mkdir(parents=True, exist_ok=True)
    with artifact.open("wb") as fh:
        for _ in range(16):
            fh.write(b"Y" * 4096)
            fh.flush()
        fh.write(COMPLETE)
        fh.flush()
        os.fsync(fh.fileno())


def idle_heartbeat(artifact: Path, heartbeat: Path) -> None:
    artifact.parent.mkdir(parents=True, exist_ok=True)
    heartbeat.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(b"idle-start\n")
    seq = 0
    while True:
        seq += 1
        heartbeat.write_text(
            json.dumps({"seq": seq, "pid": os.getpid()}, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        t0 = time.monotonic()
        while time.monotonic() - t0 < 0.01:
            pass
        time.sleep(0.05)


def harvest_remote(ledger: Path, artifact: Path, unit_id: str, delay_s: float) -> None:
    ledger.parent.mkdir(parents=True, exist_ok=True)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    _append_ledger(
        ledger,
        {"event": "spawn", "unit_id": unit_id, "role": "remote-worker"},
    )
    artifact.write_bytes(b"remote-partial\n")
    time.sleep(max(0.15, delay_s))
    with artifact.open("ab") as fh:
        fh.write(b"remote-done\n")
        fh.write(COMPLETE)
        fh.flush()
        os.fsync(fh.fileno())
    _append_ledger(
        ledger,
        {
            "event": "terminal",
            "unit_id": unit_id,
            "exit_code": 0,
            "reason": "remote-finished-after-monitor-death",
            "bytes": artifact.stat().st_size,
        },
    )


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("FAILED:worker usage", file=sys.stderr)
        return 2
    mode = argv[1]
    if mode == "write-forever":
        write_forever(Path(argv[2]))
    elif mode == "write-complete":
        write_complete(Path(argv[2]))
    elif mode == "idle-heartbeat":
        idle_heartbeat(Path(argv[2]), Path(argv[3]))
    elif mode == "harvest-remote":
        delay = float(argv[5]) if len(argv) > 5 else 0.4
        harvest_remote(Path(argv[2]), Path(argv[3]), argv[4], delay)
    else:
        print(f"FAILED:worker unknown mode {mode}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
