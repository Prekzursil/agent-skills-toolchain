#!/usr/bin/env python3
"""Probe 2: negative control — empty declared category prevents coverage PASS.

Starts from the fixture counts (independent Counter), not the author's
receipt prose. Also records both-states: fill gamma → coverage PASS.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import (  # noqa: E402
    declared,
    evaluate,
    independent_counts,
    load,
    result_by_id,
    spec,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0301-probe2 {msg}")
    return 1


def main() -> int:
    council = spec()
    empty = load("snapshot_empty_gamma.json")
    cats = declared()
    ind = independent_counts(empty["ideas"], cats)
    if ind.get("gamma", 0) != 0:
        return fail(f"negative fixture gamma count={ind.get('gamma')}")
    occupied = sum(1 for v in ind.values() if v > 0)
    agg = occupied / len(cats)
    if agg < 0.5:
        return fail(f"disagreement fixture broken aggregate={agg}")

    report = evaluate(council, empty)
    cov = result_by_id(report, "t-coverage")
    if cov.get("pass") is not False:
        return fail("empty declared category must prevent coverage PASS")
    if "gamma" not in (cov.get("empty_categories") or []):
        return fail("empty category gamma not listed explicitly")
    if cov.get("aggregate_would_pass") is not True:
        return fail("aggregate must still pass so the two rules disagree")
    if cov.get("aggregate_and_per_category_disagree") is not True:
        return fail("evaluator did not flag aggregate vs per-category disagreement")

    filled = copy.deepcopy(empty)
    filled["ideas"].append(
        {"id": "g1", "category": "gamma", "text": "gamma fills the empty declared category"}
    )
    ind2 = independent_counts(filled["ideas"], cats)
    if ind2["gamma"] < 1:
        return fail("both-states plant failed")
    report2 = evaluate(council, filled)
    cov2 = result_by_id(report2, "t-coverage")
    if cov2.get("pass") is not True:
        return fail("filling the empty category must make coverage PASS")
    if cov2.get("empty_categories"):
        return fail(f"filled empties={cov2.get('empty_categories')}")

    payload = {
        "probe": "probe2-empty-category-negative-control",
        "unit_id": "IMP-0301",
        "pass": True,
        "independent_counts_empty_gamma": ind,
        "independent_counts_filled": ind2,
        "coverage_pass_empty_gamma": False,
        "coverage_pass_filled": True,
        "empty_categories_listed": cov.get("empty_categories"),
        "aggregate_occupied_fraction": cov.get("occupied_fraction_aggregate"),
        "aggregate_would_pass": True,
        "per_category_pass": False,
        "disagree": True,
        "negative_control": (
            "empty declared category gamma prevents coverage PASS; "
            "occupied-fraction aggregate 2/3 would pass a 0.5 threshold"
        ),
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:IMP-0301-probe2 empty category prevents coverage PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
