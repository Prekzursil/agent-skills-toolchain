#!/usr/bin/env python3
"""Fixture child for hang-detection probes.

Modes:
  hung       — freeze heartbeat and output (both signals dead)
  bytes      — grow output, freeze heartbeat (slow-but-alive via byte-growth)
  heartbeat  — advance heartbeat, freeze output
  both       — advance both signals
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path


def write_hb(path: Path, token: int) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps({"token": int(token)}) + "\n", encoding="utf-8")
    tmp.replace(path)


def main() -> int:
    if len(sys.argv) < 4:
        print("usage: worker.py MODE HEARTBEAT_PATH OUTPUT_PATH [INTERVAL]", file=sys.stderr)
        return 2
    mode = sys.argv[1]
    hb = Path(sys.argv[2])
    out = Path(sys.argv[3])
    interval = float(sys.argv[4]) if len(sys.argv) > 4 else 0.05
    hb.parent.mkdir(parents=True, exist_ok=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_hb(hb, 0)
    out.write_bytes(b"")
    token = 0
    while True:
        if mode == "hung":
            time.sleep(interval)
        elif mode == "bytes":
            with out.open("ab") as fh:
                fh.write(b"x")
                fh.flush()
            time.sleep(interval)
        elif mode == "heartbeat":
            token += 1
            write_hb(hb, token)
            time.sleep(interval)
        elif mode == "both":
            token += 1
            write_hb(hb, token)
            with out.open("ab") as fh:
                fh.write(b"x")
                fh.flush()
            time.sleep(interval)
        else:
            print(f"unknown mode {mode!r}", file=sys.stderr)
            return 2


if __name__ == "__main__":
    raise SystemExit(main())
