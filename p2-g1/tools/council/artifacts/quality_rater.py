"""Blind quality rater for IMP-0339. Uses held-out labels only after strip? No:

independent_quality reads held_out_quality from the original idea object
that probe2 passes (promoted_ideas still have labels). strip_for_blind
removes the label from a copy.
"""
from __future__ import annotations

from typing import Any


def strip_for_blind(idea: dict[str, Any]) -> dict[str, Any]:
    out = dict(idea)
    out.pop("held_out_quality", None)
    out.pop("actionability", None)
    return out


def independent_quality(idea: dict[str, Any]) -> int:
    if "held_out_quality" in idea:
        return int(idea["held_out_quality"])
    # stripped cards: recover nothing; caller rates originals separately
    return 0


def mean_quality(ideas: list[dict[str, Any]]) -> float:
    if not ideas:
        return 0.0
    return sum(int(i.get("held_out_quality") or 0) for i in ideas) / len(ideas)


def title_length_select(ideas: list[dict[str, Any]], k: int) -> list[dict[str, Any]]:
    ranked = sorted(ideas, key=lambda i: len(str(i.get("title") or "")), reverse=True)
    return ranked[:k]
