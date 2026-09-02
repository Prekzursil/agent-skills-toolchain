#!/usr/bin/env python3
"""Probe 1: leakage scan of the judge-visible tree plus detector control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pipeline as P  # noqa: E402
from identities import enumerated_literals  # noqa: E402
from leakage import plant_and_scan, scan_tree  # noqa: E402

PLANT = "marketplace-first"


def main() -> int:
    if not P.ENTRIES_ROOT.is_dir() or not any(P.ENTRIES_ROOT.iterdir()):
        P.build()
    scan = scan_tree(P.JUDGE_ROOT)
    plant = plant_and_scan("judge-visible body with no listed identity tokens\n", PLANT)
    print(
        json.dumps(
            {
                "pattern_count": len(enumerated_literals()),
                "file_count": scan["file_count"],
                "hit_count": scan["hit_count"],
                "detector_fired": plant["detector_fired"],
                "plant": PLANT,
            },
            sort_keys=True,
        )
    )
    if scan["hit_count"] != 0:
        print(f"FAILED:ARC-0067-probe1 leakage hits={scan['hits'][:8]}")
        return 1
    if not plant["detector_fired"]:
        print("FAILED:ARC-0067-probe1 detector control did not fire on planted name")
        return 1
    if plant["clean_hits"] != 0:
        print("FAILED:ARC-0067-probe1 control body was not clean")
        return 1
    print("SUCCESS:ARC-0067-probe1 leakage-zero and detector-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
