#!/usr/bin/env python3
"""IMP-0165 probe 2: UNKNOWN rate computed over the whole candidate set.

Mechanically different from probe 1 (per-string mapping). This probe
extracts every participant in the labelled imported-workflow set, recounts
UNKNOWN/total independently of unknown_rate(), and checks that injecting
one extra UNKNOWN raises the number.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from scenario import candidate_set_rate  # noqa: E402


def main() -> int:
    result = candidate_set_rate()
    payload = {
        "probe": "probe2-unknown-rate",
        "unit_id": "IMP-0165",
        "pass": bool(result["pass"]),
        "stats": result["stats"],
        "labels": result["labels"],
        "recount_rate": result["recount_rate"],
        "zero_subset_rate": result["zero_subset_rate"],
        "mutated_rate": result["mutated_rate"],
        "label_match": result["label_match"],
        "computed": result["computed"],
        "rate_moves_on_extra_unknown": result["rate_moves_on_extra_unknown"],
        "both_states_rate": result["both_states_rate"],
        "mismatches": result["mismatches"],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:IMP-0165-probe2 UNKNOWN rate not computed over whole set")
        return 1
    stats = result["stats"]
    print(
        f"unknown_rate={stats['rate']} unknown={stats['unknown']}/{stats['total']}"
    )
    print("SUCCESS:IMP-0165-probe2 UNKNOWN rate is a computed number over the whole candidate set")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
