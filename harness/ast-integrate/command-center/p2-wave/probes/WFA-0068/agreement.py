"""Per-disposition agreement. Aggregate accuracy is reported and is not the gate."""
from __future__ import annotations

from typing import Any

from vocabulary import VOCABULARY

AGREEMENT_FLOOR = 1.0


def binary_kappa(truth: list[int], pred: list[int]) -> float | None:
    n = len(truth)
    if n == 0 or len(pred) != n:
        return None
    tp = sum(1 for t, p in zip(truth, pred) if t == 1 and p == 1)
    tn = sum(1 for t, p in zip(truth, pred) if t == 0 and p == 0)
    fp = sum(1 for t, p in zip(truth, pred) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(truth, pred) if t == 1 and p == 0)
    po = (tp + tn) / n
    p_true = (tp + fn) / n
    p_pred = (tp + fp) / n
    pe = p_true * p_pred + (1 - p_true) * (1 - p_pred)
    if pe == 1.0:
        return 1.0 if po == 1.0 else 0.0
    return (po - pe) / (1.0 - pe)


def per_disposition(gold: list[str], pred: list[str]) -> list[dict[str, Any]]:
    if len(gold) != len(pred):
        raise ValueError("gold/pred length mismatch")
    rows: list[dict[str, Any]] = []
    for value in VOCABULARY:
        t = [1 if g == value else 0 for g in gold]
        p = [1 if x == value else 0 for x in pred]
        n_gold = sum(t)
        n_pred = sum(p)
        n_tp = sum(1 for a, b in zip(t, p) if a == 1 and b == 1)
        rate = (n_tp / n_gold) if n_gold else None
        precision = (n_tp / n_pred) if n_pred else None
        rows.append(
            {
                "disposition": value,
                "n_gold": n_gold,
                "n_pred": n_pred,
                "n_true_positive": n_tp,
                "recall": rate,
                "precision": precision,
                "kappa": binary_kappa(t, p),
                "meets_floor": (rate == AGREEMENT_FLOOR) if n_gold else None,
            }
        )
    return rows


def aggregate_accuracy(gold: list[str], pred: list[str]) -> float:
    if not gold:
        return 0.0
    return sum(1 for g, p in zip(gold, pred) if g == p) / len(gold)


def passes_floor(rows: list[dict[str, Any]]) -> bool:
    scored = [r for r in rows if r["n_gold"] >= 1]
    if not scored:
        return False
    return all(r["meets_floor"] is True and r["n_pred"] == r["n_gold"] for r in scored)
