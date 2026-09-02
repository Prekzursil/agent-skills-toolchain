#!/usr/bin/env python3
"""Probe 1: planted renamed copy is discounted; planted distinct survives.

Uses the Jaccard/normalized-name clusterer (method B). Independent of
probe 2's fingerprint clusterer and of the source-class set difference.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from candidates import (  # noqa: E402
    PLANT_DISTINCT_ID,
    PLANT_RENAME_ID,
    build_array,
    plant_distinct,
    plant_renamed_copy,
)
from fork_discount import discount  # noqa: E402

UNIT = "WFA-0160"


def main() -> int:
    base = build_array()
    planted = base + [plant_renamed_copy(), plant_distinct()]
    result = discount(planted, method="jaccard")
    dropped = set(result["dropped_ids"])
    kept = set(result["kept_ids"])
    rename_dropped = PLANT_RENAME_ID in dropped
    distinct_survived = PLANT_DISTINCT_ID in kept and PLANT_DISTINCT_ID not in dropped
    in_array_fork_dropped = "wf-saved-agentic-repair-reliability-copy" in dropped
    original_kept = "wf-saved-agentic-repair-reliability" in kept
    ok = (
        rename_dropped
        and distinct_survived
        and in_array_fork_dropped
        and original_kept
        and result["raw_count"] == 286
        and result["discounted_count"] == result["raw_count"] - len(dropped)
        and len(dropped) >= 2
    )
    payload = {
        "probe": "probe1-planted-discount",
        "unit_id": UNIT,
        "method": "jaccard",
        "raw_count": result["raw_count"],
        "discounted_count": result["discounted_count"],
        "dropped_n": len(dropped),
        "rename_plant_dropped": rename_dropped,
        "distinct_plant_survived": distinct_survived,
        "in_array_fork_dropped": in_array_fork_dropped,
        "original_kept": original_kept,
        "pass": ok,
    }
    print(json.dumps(payload, sort_keys=True))
    if not ok:
        print(f"FAILED:{UNIT}-probe1 planted discount both-states")
        return 1
    print(
        f"SUCCESS:{UNIT}-probe1 renamed-copy-removed distinct-survived "
        f"dropped={len(dropped)} discounted={result['discounted_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
