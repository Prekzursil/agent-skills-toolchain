"""Score gold records with both classifiers. Does not trust stored labels as input."""
from __future__ import annotations

from typing import Any

from agreement import AGREEMENT_FLOOR, aggregate_accuracy, passes_floor, per_disposition
from decide import decide
from gold_set import (
    assert_gold_invariants,
    disposition_coverage,
    family_coverage,
    gold_records,
)
from independent import decide_independent


def score_gold(records: list[dict] | None = None) -> dict[str, Any]:
    assert_gold_invariants()
    rows = records if records is not None else gold_records()
    author = [decide(r) for r in rows]
    indep = [decide_independent(r) for r in rows]
    gold = [str(r["gold"]) for r in rows]
    pred_a = [str(d["disposition"]) for d in author]
    pred_b = [str(d["disposition"]) for d in indep]
    per_a = per_disposition(gold, pred_a)
    per_b = per_disposition(gold, pred_b)
    pair_agree = sum(1 for a, b in zip(pred_a, pred_b) if a == b)
    labelled = []
    for rec, a, b in zip(rows, author, indep):
        labelled.append(
            {
                "id": rec["id"],
                "family": rec["family"],
                "gold": rec["gold"],
                "author": a["disposition"],
                "independent": b["disposition"],
                "author_reason": a["reason"],
                "author_fired": a["fired"],
                "independent_fired": b["fired"],
                "missing_input": a.get("missing_input"),
                "match_gold": a["disposition"] == rec["gold"],
            }
        )
    return {
        "n": len(rows),
        "author_per_disposition": per_a,
        "independent_per_disposition": per_b,
        "author_aggregate_accuracy": aggregate_accuracy(gold, pred_a),
        "independent_aggregate_accuracy": aggregate_accuracy(gold, pred_b),
        "author_meets_floor": passes_floor(per_a),
        "independent_meets_floor": passes_floor(per_b),
        "author_independent_agree_n": pair_agree,
        "author_independent_agree": pair_agree == len(rows),
        "agreement_floor": AGREEMENT_FLOOR,
        "family_coverage": family_coverage(rows),
        "disposition_coverage": disposition_coverage(rows),
        "records": labelled,
        "no_rule_fired": [d["id"] for d in author if d["disposition"] is None],
    }
