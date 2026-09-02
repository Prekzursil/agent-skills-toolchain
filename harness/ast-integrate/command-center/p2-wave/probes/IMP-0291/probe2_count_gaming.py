#!/usr/bin/env python3
"""Named probe 2: spec 11339 count-gaming control + labelled grouping score.

Mechanically different from probe 1 (which scores a 5-row mixed ledger).
This probe plants 100 trivial wordings of one mechanism and asserts the
stopping counter (mechanism_distinct) does NOT meet unique_ideas>=100,
while a string-only counter WOULD. A genuinely distinct idea is still
accepted. Independently, a hand-labelled sample of 40 ideas is scored.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from reviewer import review_labelled_grouping  # noqa: E402
from scenario import evaluate_count_gaming, evaluate_labelled_sample  # noqa: E402


def main() -> int:
    gaming = evaluate_count_gaming()
    labelled = evaluate_labelled_sample()
    review = review_labelled_grouping()
    payload = {
        "probe": "probe2-count-gaming",
        "unit_id": "IMP-0291",
        "count_gaming": gaming,
        "labelled_sample": {
            k: v for k, v in labelled.items() if k != "rows"
        },
        "reviewer": review,
        "pass": bool(gaming["pass"] and labelled["pass"] and review["pass"]),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:IMP-0291-probe2 count-gaming or labelled grouping")
        return 1
    print(
        "string_distinct={0} mechanism_distinct={1} gaming={2} labelled_f1={3}".format(
            gaming["counts_before_distinct"]["string_distinct"],
            gaming["counts_before_distinct"]["mechanism_distinct"],
            gaming["count_gaming_detected"],
            labelled["score"]["f1"],
        )
    )
    print(
        "SUCCESS:IMP-0291-probe2 100 wording variants do not meet "
        "unique_ideas>=100; 40-idea grouping f1=1.0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
