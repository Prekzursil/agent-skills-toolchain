"""Offer-recall and measured-cost pairing for TST-0318.

Recall is 'was the gold capability offered' (in the injected set), not
top-1 identity. A recall figure with no cost figure is the degenerate
result this unit exists to prevent.
"""
from __future__ import annotations

from typing import Any

from router import FALLBACK_ID, TOKEN_BUDGET


def offered(pred: dict[str, Any]) -> set[str]:
    return {str(x) for x in (pred.get("offered_ids") or [])}


def gold_offered(case: dict[str, Any], pred: dict[str, Any]) -> bool:
    return str(case["expected"]) in offered(pred)


def pair_ok(pred: dict[str, Any]) -> bool:
    """Both axes present: recall is computed by the caller; cost must be measured."""
    cost = pred.get("injected_token_cost")
    est = pred.get("estimated_token_cost")
    return isinstance(cost, int) and cost >= 0 and isinstance(est, int)


def micro_offer_recall(
    cases: list[dict[str, Any]], predictions: list[dict[str, Any]]
) -> float:
    if len(cases) != len(predictions) or not cases:
        raise ValueError("cases/predictions length mismatch")
    hits = sum(1 for c, p in zip(cases, predictions) if gold_offered(c, p))
    return hits / len(cases)


def per_capability_offer_table(
    cases: list[dict[str, Any]], predictions: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    if len(cases) != len(predictions):
        raise ValueError("cases/predictions length mismatch")
    ids = sorted({str(c["expected"]) for c in cases})
    rows: dict[str, dict[str, Any]] = {}
    for cid in ids:
        tp = fn = 0
        for case, pred in zip(cases, predictions):
            gold = str(case["expected"])
            if gold != cid:
                continue
            if gold_offered(case, pred):
                tp += 1
            else:
                fn += 1
        gold_n = tp + fn
        rows[cid] = {
            "capability_id": cid,
            "tp": tp,
            "fn": fn,
            "gold": gold_n,
            "recall": (tp / gold_n) if gold_n else None,
            "is_fallback": cid == FALLBACK_ID,
        }
    return rows


def mean_cost(predictions: list[dict[str, Any]]) -> float:
    if not predictions:
        return 0.0
    return sum(int(p["injected_token_cost"]) for p in predictions) / len(predictions)


def max_cost(predictions: list[dict[str, Any]]) -> int:
    if not predictions:
        return 0
    return max(int(p["injected_token_cost"]) for p in predictions)


def all_under_budget(predictions: list[dict[str, Any]]) -> bool:
    return all(int(p["injected_token_cost"]) <= TOKEN_BUDGET for p in predictions)


def all_over_budget(predictions: list[dict[str, Any]]) -> bool:
    return all(int(p["injected_token_cost"]) > TOKEN_BUDGET for p in predictions)


def composite_cell_pass(case: dict[str, Any], pred: dict[str, Any]) -> bool:
    """Non-degenerate cell: gold offered AND measured cost within budget."""
    return gold_offered(case, pred) and int(pred["injected_token_cost"]) <= TOKEN_BUDGET


def configuration_pair(
    policy: str,
    cases: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
) -> dict[str, Any]:
    recall = micro_offer_recall(cases, predictions)
    mean = mean_cost(predictions)
    peak = max_cost(predictions)
    under = all_under_budget(predictions)
    over = all_over_budget(predictions)
    return {
        "policy": policy,
        "recall": recall,
        "injected_token_cost_mean": mean,
        "injected_token_cost_max": peak,
        "budget_limit": TOKEN_BUDGET,
        "budget_ok": under,
        "budget_failed": over or (not under),
        "n_tasks": len(cases),
        "pair_complete": all(pair_ok(p) for p in predictions),
        "used_decoy_estimate": all(
            int(p["injected_token_cost"]) == int(p["estimated_token_cost"])
            for p in predictions
        )
        and any(int(p["injected_token_cost"]) > 0 for p in predictions),
    }
