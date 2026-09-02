"""Calibrated participant selection by Brier/log score (IMP-0268)."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

LOG_CLIP = 1e-15


def _forecasts(store: dict[str, Any], pid: str) -> list[tuple[float, int]]:
    rec = (store.get("participants") or {}).get(pid) or {}
    out: list[tuple[float, int]] = []
    for item in rec.get("forecasts") or []:
        out.append((float(item["p"]), int(item["outcome"])))
    return out


def brier_score(forecasts: list[tuple[float, int]]) -> float:
    return sum((p - o) ** 2 for p, o in forecasts) / len(forecasts)


def log_score(forecasts: list[tuple[float, int]]) -> float:
    total = 0.0
    for p, o in forecasts:
        q = min(1.0 - LOG_CLIP, max(LOG_CLIP, p))
        total += -(o * math.log(q) + (1 - o) * math.log(1.0 - q))
    return total / len(forecasts)


def _load_store(store: Any) -> dict[str, Any]:
    if isinstance(store, dict):
        return store
    path = Path(store)
    if not path.is_file():
        return {"participants": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def select_calibrated(
    candidates: list[str],
    store: Any,
    metric: str = "brier",
    min_resolved: int = 10,
) -> dict[str, Any]:
    doc = _load_store(store)
    scorer = brier_score if metric == "brier" else log_score
    table: list[dict[str, Any]] = []
    for pid in candidates:
        fc = _forecasts(doc, pid)
        n = len(fc)
        if n < min_resolved:
            table.append(
                {
                    "participant_id": pid,
                    "n_resolved": n,
                    "score": None,
                    "eligible": False,
                }
            )
            continue
        table.append(
            {
                "participant_id": pid,
                "n_resolved": n,
                "score": scorer(fc),
                "eligible": True,
            }
        )
    eligible = [r for r in table if r["eligible"]]
    if not eligible:
        event = "missing-file" if not Path(str(store)).is_file() and not isinstance(store, dict) else "empty-store"
        return {
            "strategy_used": "degraded:explicit-order",
            "degradation": {
                "loud": True,
                "event": event,
                "fallback": "explicit-order",
            },
            "confident_ranking": False,
            "ranking": [],
            "score_table": [],
            "seated": [],
        }
    ranking = sorted(eligible, key=lambda r: (float(r["score"]), r["participant_id"]))
    rank_ids = [r["participant_id"] for r in ranking]
    # keep ineligible at end in candidate order
    for pid in candidates:
        if pid not in rank_ids:
            rank_ids.append(pid)
    seated = [
        {"participant_id": pid, "score": next(r["score"] for r in ranking if r["participant_id"] == pid)}
        for pid in rank_ids
        if any(r["participant_id"] == pid and r["eligible"] for r in table)
    ]
    return {
        "strategy_used": "calibration",
        "degradation": None,
        "confident_ranking": True,
        "ranking": rank_ids,
        "seated": seated,
        "score_table": table,
        "metric": metric,
    }


__all__ = ["brier_score", "log_score", "select_calibrated"]
