#!/usr/bin/env python3
"""Naive in-place chunked writer - the mutation control for IMP-0224 probe 2.

Writes the PUBLISHED path directly (no staging, no atomic replace). Killed mid-write it
leaves a torn tail, which the schema check must catch. This is the defect twin that proves
the probe discriminates against the LedgerWriter staging+replace protocol.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--path", required=True)
    p.add_argument("--payload-bytes", type=int, default=4096)
    p.add_argument("--chunk-size", type=int, default=96)
    args = p.parse_args()
    dest = Path(args.path)
    payload = "y" * int(args.payload_bytes)
    blob = (
        json.dumps({"payload": payload, "unit_id": "IMP-0224-naive", "phase": "7"})
        + "\n"
    ).encode("utf-8")
    with dest.open("ab") as fh:
        step = max(1, int(args.chunk_size))
        for i in range(0, len(blob), step):
            fh.write(blob[i : i + step])
            fh.flush()
            time.sleep(0.002)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
