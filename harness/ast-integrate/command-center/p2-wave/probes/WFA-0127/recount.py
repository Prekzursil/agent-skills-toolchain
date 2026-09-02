"""Independent overlap recount used by probe2 (does not import scout ranking)."""
from __future__ import annotations

from typing import Any


def jaccard(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / float(len(sa | sb))


def coverage(goal: list[str], cand: list[str]) -> float:
    need = set(goal)
    if not need:
        return 0.0
    return len(need & set(cand)) / float(len(need))


def score_row(goal_mechs: list[str], cand: dict[str, Any]) -> dict[str, Any]:
    mechs = [str(m) for m in (cand.get("mechanisms") or [])]
    return {
        "id": cand.get("id"),
        "coverage": coverage(goal_mechs, mechs),
        "jaccard": jaccard(goal_mechs, mechs),
        "quality": float(cand.get("quality") or 0.0),
        "licence_class": cand.get("licence_class"),
        "source_class": cand.get("source_class"),
        "mechanisms": mechs,
    }
