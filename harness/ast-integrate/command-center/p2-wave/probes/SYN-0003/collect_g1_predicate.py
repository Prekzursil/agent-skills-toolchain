#!/usr/bin/env python3
"""Discriminating collector: leftover vs G-1 measure (cloud ok not consulted)."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MEASURE = REPO / "command-center/p2-wave/_measure_one_delivered.py"
LEFTOVER = REPO / "command-center/p2-wave/P2-CLOUD-LEFTOVER_2026-08-24.json"
PROBES = REPO / "command-center/p2-wave/probes"
NEEDLE = "cloud ok=true is not consulted"


def main() -> int:
    src = MEASURE.read_text(encoding="utf-8") if MEASURE.is_file() else ""
    leftover_has = False
    remaining_n = 0
    if LEFTOVER.is_file():
        data = json.loads(LEFTOVER.read_text(encoding="utf-8"))
        ids = data.get("remaining_ids") or []
        remaining_n = len(ids)
        leftover_has = "SYN-0003" in ids
    probe_dirs = [p.name for p in PROBES.glob("SYN-*") if p.is_dir()] if PROBES.is_dir() else []
    print(
        json.dumps(
            {
                "collector": "g1-predicate",
                "measure_declines_cloud_ok": NEEDLE in src,
                "leftover_lists_SYN-0003": leftover_has,
                "leftover_remaining_n": remaining_n,
                "syn_probe_dirs": probe_dirs,
                "syn0003_probe_dir_present": "SYN-0003" in probe_dirs,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
