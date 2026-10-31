"""Deterministic roadmap ranking from recorded inputs only."""
from __future__ import annotations

from typing import Any, Mapping


class RankingRefusal(Exception):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


_REQUIRED_FIELDS = ("reach", "impact", "confidence", "effort")


def rank(payload: Mapping[str, Any]) -> dict[str, Any]:
    if "weights" not in payload:
        raise RankingRefusal("ranking-weights-missing", "weights omitted")
    weights = payload.get("weights")
    if not isinstance(weights, dict) or any(k not in weights for k in _REQUIRED_FIELDS):
        raise RankingRefusal("ranking-weights-missing", "weights incomplete")
    items = list(payload.get("items") or [])
    scored: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict) or "id" not in item:
            raise RankingRefusal("ranking-item-incomplete", "item missing id")
        for field in _REQUIRED_FIELDS:
            if field not in item:
                raise RankingRefusal("ranking-item-incomplete", f"missing {field}")
        reach = float(item["reach"])
        impact = float(item["impact"])
        confidence = float(item["confidence"])
        effort = float(item["effort"])
        w_r = float(weights["reach"])
        w_i = float(weights["impact"])
        w_c = float(weights["confidence"])
        w_e = float(weights["effort"])
        score = (reach * w_r) * (impact * w_i) * ((confidence / 100.0) * w_c) / max(
            effort * w_e, 1e-12
        )
        scored.append({"id": str(item["id"]), "score": score})
    scored.sort(key=lambda row: (-row["score"], row["id"]))
    return {
        "ranking": scored,
        "ranking_ids": [row["id"] for row in scored],
        "hidden_state": False,
        "arithmetic": "weighted-rice",
        "workflow_id": "wf.roadmap-prioritization",
    }
