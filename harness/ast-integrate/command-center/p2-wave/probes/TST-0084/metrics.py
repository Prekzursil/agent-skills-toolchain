"""Per-capability recall/precision. A headline average that hides a zero-recall
capability is an overclaim (catalog evidence_requirement).
"""
from __future__ import annotations

from typing import Any

from router import FALLBACK_ID


def per_capability_table(
    cases: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    if len(cases) != len(predictions):
        raise ValueError("cases/predictions length mismatch")
    gold_ids: set[str] = set()
    pred_ids: set[str] = set()
    for case, pred in zip(cases, predictions):
        gold_ids.add(str(case["expected"]))
        pred_ids.add(str(pred["capability_id"]))
    ids = sorted(gold_ids | pred_ids)
    rows: dict[str, dict[str, Any]] = {}
    for cid in ids:
        tp = fp = fn = 0
        for case, pred in zip(cases, predictions):
            gold = str(case["expected"])
            got = str(pred["capability_id"])
            if gold == cid and got == cid:
                tp += 1
            elif gold == cid and got != cid:
                fn += 1
            elif gold != cid and got == cid:
                fp += 1
        gold_n = tp + fn
        pred_n = tp + fp
        recall = (tp / gold_n) if gold_n else None
        precision = (tp / pred_n) if pred_n else None
        rows[cid] = {
            "capability_id": cid,
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "gold": gold_n,
            "predicted": pred_n,
            "recall": recall,
            "precision": precision,
            "is_fallback": cid == FALLBACK_ID,
        }
    return rows


def macro_recall(table: dict[str, dict[str, Any]], *, skip_fallback: bool = False) -> float:
    vals = []
    for row in table.values():
        if skip_fallback and row.get("is_fallback"):
            continue
        if row["gold"] <= 0:
            continue
        if row["recall"] is None:
            continue
        vals.append(float(row["recall"]))
    if not vals:
        return 0.0
    return sum(vals) / len(vals)


def micro_recall(table: dict[str, dict[str, Any]]) -> float:
    tp = sum(int(r["tp"]) for r in table.values())
    gold = sum(int(r["gold"]) for r in table.values())
    return (tp / gold) if gold else 0.0


def zero_recall_capabilities(table: dict[str, dict[str, Any]]) -> list[str]:
    out = []
    for cid, row in table.items():
        if int(row["gold"]) > 0 and row["recall"] == 0:
            out.append(cid)
    return sorted(out)


def overclaim_hidden_zero(
    table: dict[str, dict[str, Any]],
    headline: float,
    *,
    headline_floor: float = 0.5,
) -> dict[str, Any]:
    """True when a headline average would hide a labelled capability with recall 0."""
    zeros = zero_recall_capabilities(table)
    hidden = bool(zeros) and headline >= headline_floor
    return {
        "hidden_zero_recall": hidden,
        "zero_recall_capabilities": zeros,
        "headline": headline,
        "headline_floor": headline_floor,
        "reason": (
            "headline average hides zero-recall capability"
            if hidden
            else "per-capability zeros reported or absent"
        ),
    }
