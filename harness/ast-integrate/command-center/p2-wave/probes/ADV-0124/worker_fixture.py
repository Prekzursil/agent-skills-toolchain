#!/usr/bin/env python3
"""Fixture processes for ADV-0124 constructed states.

Modes:
  busy <artifact>       — CPU + growing incomplete artifact
  finish <artifact>     — writes COMPLETE trailer and exits 0
  heartbeat <hb.json>   — independent monitor heartbeat sequence
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

COMPLETE = b"\nADV-0124-COMPLETE\n"


def busy(artifact: Path) -> None:
    artifact.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with artifact.open("wb") as fh:
        while True:
            fh.write(b"W" * 4096)
            fh.flush()
            t0 = time.monotonic()
            while time.monotonic() - t0 < 0.02:
                n += 1
            time.sleep(0.01)


def finish(artifact: Path) -> None:
    artifact.parent.mkdir(parents=True, exist_ok=True)
    with artifact.open("wb") as fh:
        for _ in range(8):
            fh.write(b"F" * 4096)
        fh.write(COMPLETE)
        fh.flush()
        os.fsync(fh.fileno())


def heartbeat(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    seq = 0
    while True:
        seq += 1
        path.write_text(
            json.dumps({"seq": seq, "pid": os.getpid()}, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        time.sleep(0.05)


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print("FAILED:worker_fixture usage", file=sys.stderr)
        return 2
    mode = argv[1]
    target = Path(argv[2])
    if mode == "busy":
        busy(target)
    elif mode == "finish":
        finish(target)
    elif mode == "heartbeat":
        heartbeat(target)
    else:
        print(f"FAILED:worker_fixture unknown mode {mode}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
