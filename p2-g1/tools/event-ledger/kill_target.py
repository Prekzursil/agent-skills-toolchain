#!/usr/bin/env python3
"""Slow atomic JSONL append so a probe can SIGKILL mid-write."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ledger as L  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--path", required=True)
    p.add_argument("--mode", default="atomic")
    p.add_argument("--payload-bytes", type=int, default=1024)
    p.add_argument("--chunk-size", type=int, default=256)
    args = p.parse_args()
    dest = Path(args.path)
    staging = dest.with_name(dest.name + ".staging")
    payload = "x" * int(args.payload_bytes)
    rec = {"payload": payload, "unit_id": "IMP-0224", "phase": "7"}
    blob = json.dumps(rec) + "\n"
    current = dest.read_bytes() if dest.is_file() else b""
    # expose staging so the probe can observe it, then write slowly
    staging.write_bytes(current)
    time.sleep(0.05)
    with staging.open("ab") as fh:
        data = blob.encode("utf-8")
        step = max(1, int(args.chunk_size))
        for i in range(0, len(data), step):
            fh.write(data[i : i + step])
            fh.flush()
            time.sleep(0.002)
    staging.replace(dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
