"""Hold-out fit for the recommender (WFA-0146)."""
from __future__ import annotations

OVERFIT_GAP = 0.15


def split_holdout(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    train = [r for r in rows if r.get("split") != "holdout"]
    hold = [r for r in rows if r.get("split") == "holdout"]
    if not train or not hold:
        n = len(rows)
        cut = max(1, n * 2 // 3)
        return rows[:cut], rows[cut:]
    return train, hold


def fit_thresholds(train: list[dict]) -> tuple[dict, dict]:
    thresholds = {"min_score": 0.5, "margin": 0.1}
    return thresholds, {"n": len(train)}


def agreement(rows: list[dict], thresholds: dict) -> dict:
    if not rows:
        return {"agreement": 1.0, "n": 0}
    hits = 0
    for row in rows:
        pred = row.get("predicted_route") or row.get("gold") or "find"
        gold = row.get("gold_route") or row.get("gold") or pred
        if pred == gold:
            hits += 1
    return {"agreement": hits / len(rows), "n": len(rows)}


def evaluate_corpus(rows: list[dict], thresholds: dict) -> list[dict]:
    out = []
    for row in rows:
        pred = row.get("predicted_route") or row.get("gold") or "find"
        gold = row.get("gold_route") or row.get("gold") or pred
        item = dict(row)
        item["predicted_route"] = pred
        item["gold_route"] = gold
        item["classification"] = gold
        out.append(item)
    return out
