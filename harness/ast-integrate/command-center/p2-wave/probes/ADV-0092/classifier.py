"""Frozen role-mandate prototype classifier.

Input is brief text only. Role labels are revealed after each prediction.
Does not import probe1 statistics or stance fields.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence

from councils import PROTOTYPES
from common import CHANCE_ACCURACY, ROLES
from metrics import binomial_tail_ge, tokens, jaccard_similarity


def predict_role(text: str) -> tuple[str, float, dict[str, float]]:
    bag = tokens(text)
    scores = {
        role: jaccard_similarity(bag, tokens(proto)) for role, proto in PROTOTYPES.items()
    }
    best_role = max(ROLES, key=lambda r: (scores[r], r))
    return best_role, scores[best_role], scores


def attribute(dataset: str, briefs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    rows = []
    correct = 0
    predicted_counts: Counter[str] = Counter()
    for item in briefs:
        predicted, best, scores = predict_role(str(item.get("text") or ""))
        truth = str(item.get("role") or "")
        ok = predicted == truth
        if ok:
            correct += 1
        predicted_counts[predicted] += 1
        rows.append(
            {
                "dataset": dataset,
                "item": str(item.get("id") or ""),
                "predicted": predicted,
                "truth_revealed_after_prediction": truth,
                "correct": ok,
                "best_score": best,
                "scores": scores,
            }
        )
    n = len(rows)
    accuracy = (correct / n) if n else 0.0
    return {
        "dataset": dataset,
        "n": n,
        "correct": correct,
        "accuracy": accuracy,
        "chance": CHANCE_ACCURACY,
        "binomial_tail_p": binomial_tail_ge(correct, n, CHANCE_ACCURACY),
        "predicted_role_counts": {r: int(predicted_counts.get(r, 0)) for r in ROLES},
        "rows": rows,
    }
