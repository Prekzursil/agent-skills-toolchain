#!/usr/bin/env python3
"""Probe 1: score six artifacts; padded unresolvable citations rank lowest.

If the metric ranks the padded artifact anywhere but last, it is counting
citation shape rather than resolvability-plus-substance.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from corpus import APRIORI_BEST_TO_WORST, PADDED_ID, bodies, load_from_disk  # noqa: E402
from scorer import score_corpus  # noqa: E402


def main() -> int:
    arts = load_from_disk()
    if [a["id"] for a in arts] != APRIORI_BEST_TO_WORST:
        print("FAILED:RES-0170-probe1 fixture id order")
        return 1
    result = score_corpus(arts, bodies())
    order = result["order_best_to_worst"]
    padded_last = result["padded_is_lowest"]
    naive_first = result["naive_ranks_padded_first"]
    rho = float(result["spearman_vs_apriori"])
    by_id = {r["id"]: r for r in result["rows"]}
    composites = [by_id[i]["composite"] for i in APRIORI_BEST_TO_WORST]
    strictly_decreasing = all(composites[i] > composites[i + 1] for i in range(len(composites) - 1))
    gold_meets = bool(by_id["A1-gold"]["meets_target"])
    padded_meets = bool(by_id[PADDED_ID]["meets_target"])
    padded_resolvability = float(by_id[PADDED_ID]["scores"]["citation_resolvability"])
    gold_resolvability = float(by_id["A1-gold"]["scores"]["citation_resolvability"])
    payload = {
        "probe": "probe1-rank-and-negative-control",
        "unit_id": "RES-0170",
        "order_best_to_worst": order,
        "a_priori": APRIORI_BEST_TO_WORST,
        "padded_id": PADDED_ID,
        "padded_rank": result["padded_rank"],
        "padded_is_lowest": padded_last,
        "padded_naive_rank": result["padded_naive_rank"],
        "naive_ranks_padded_first": naive_first,
        "spearman_vs_apriori": rho,
        "strictly_decreasing_composites": strictly_decreasing,
        "composites": {i: by_id[i]["composite"] for i in APRIORI_BEST_TO_WORST},
        "resolvability": {
            "A1-gold": gold_resolvability,
            PADDED_ID: padded_resolvability,
        },
        "gold_meets_target": gold_meets,
        "padded_meets_target": padded_meets,
        "n_artifacts": len(arts),
        "pass": bool(
            padded_last
            and naive_first
            and strictly_decreasing
            and gold_meets
            and not padded_meets
            and padded_resolvability < 0.2
            and gold_resolvability >= 0.8
            and rho >= 0.9
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:RES-0170-probe1 padded artifact was not ranked lowest by substance")
        return 1
    print(
        "SUCCESS:RES-0170-probe1 six artifacts scored; padded unresolvable "
        "citations rank lowest; naive URL-count ranks them first"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
