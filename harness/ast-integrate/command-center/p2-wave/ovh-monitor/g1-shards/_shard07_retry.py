#!/usr/bin/env python3
"""Retry a subset of shard-07 named probes after module implementation."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from _shard07_win_probes import run_one  # noqa: E402

IDS = [
    "ADV-0012",
    "ADV-0032",
    "ADV-0068",
    "ADV-0090",
    "ADV-0113",
    "AUD-0088",
    "IMP-0041",
    "IMP-0068",
    "IMP-0093",
    "IMP-0142",
    "IMP-0165",
    "IMP-0207",
    "IMP-0231",
    "IMP-0268",
    "IMP-0284",
    "IMP-0309",
    "IMP-0335",
    "IMP-0389",
    "IMP-0422",
    "IMP-0450",
    "TST-0135",
]


def main() -> None:
    out = HERE / "_shard07_retry.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for uid in IDS:
            rec = run_one(uid)
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            print(uid, "OK" if rec["ok"] else "FAIL", rec.get("fails")[:1], flush=True)
    print("DONE")


if __name__ == "__main__":
    main()
