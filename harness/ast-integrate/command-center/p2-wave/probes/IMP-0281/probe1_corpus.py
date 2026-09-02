#!/usr/bin/env python3
"""Probe 1: labelled 40-turn corpus, precision and recall reported separately.

TEST_REQUIREMENT=unit: breach detection on the labelled corpus
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from corpus import TURNS, assert_shape  # noqa: E402
from tools.council.roles.guard import RoleGuard, precision_recall  # noqa: E402

UNIT = "IMP-0281"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    print(f"{UNIT} CORPUS BREACH DETECTION")
    print("TEST_REQUIREMENT=unit: breach detection on the labelled corpus")
    assert_shape()
    if len(TURNS) != 40:
        return fail(f"corpus size {len(TURNS)} != 40")

    guard = RoleGuard()
    y_true: list[bool] = []
    y_pred: list[bool] = []
    rows: list[dict] = []
    for turn in TURNS:
        result = guard.inspect(turn)
        gold_breach = turn["gold"] == "BREACH"
        y_true.append(gold_breach)
        y_pred.append(bool(result.rejected))
        rows.append(
            {
                "id": turn["id"],
                "gold": turn["gold"],
                "pred": "BREACH" if result.rejected else "MENTION",
                "classification": result.classification,
                "source": result.source,
                "attempted_action": result.attempted_action,
                "match": gold_breach == result.rejected,
            }
        )

    scores = precision_recall(y_true, y_pred)
    mismatches = [r for r in rows if not r["match"]]
    print(
        json.dumps(
            {
                "n": scores["n"],
                "breach_gold": sum(y_true),
                "mention_gold": len(y_true) - sum(y_true),
                "tp": scores["tp"],
                "fp": scores["fp"],
                "fn": scores["fn"],
                "tn": scores["tn"],
                "precision": scores["precision"],
                "recall": scores["recall"],
                "mismatches": [m["id"] for m in mismatches],
            },
            sort_keys=True,
        )
    )
    # Evidence requirement: report precision and recall separately, not an F1.
    print(f"precision={scores['precision']}")
    print(f"recall={scores['recall']}")

    if mismatches:
        print(json.dumps(mismatches[:8], indent=2))
        return fail(f"{len(mismatches)} gold/pred mismatches")
    if scores["precision"] != 1.0:
        return fail(f"precision={scores['precision']} want 1.0")
    if scores["recall"] != 1.0:
        return fail(f"recall={scores['recall']} want 1.0")
    if scores["n"] != 40 or scores["tp"] != 20 or scores["tn"] != 20:
        return fail(f"confusion {scores}")

    print(f"SUCCESS:{UNIT}-probe1 labelled-corpus precision and recall")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
