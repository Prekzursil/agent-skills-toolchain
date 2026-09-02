#!/usr/bin/env python3
"""Blind mechanism-card adjudication. Never receives lexical or cosine scores.

Independence from the embedding: cosine is a float threshold on vector angle.
This reader requires exact equality of a boolean mechanism card with minimum
weight. A pair that shares four of six axes can fire cosine and still be
DISTINCT here if the cards are not identical.
"""
from __future__ import annotations

from measures import AXES, normalize

MIN_WEIGHT = 5


def checklist(text: str) -> dict[str, bool]:
    hay = normalize(text)
    out: dict[str, bool] = {}
    for axis, phrases in AXES:
        out[axis] = any(p in hay for p in phrases)
    return out


def weight(card: dict[str, bool]) -> int:
    return sum(1 for v in card.values() if v)


def adjudicate(a_text: str, b_text: str) -> dict:
    ca = checklist(a_text)
    cb = checklist(b_text)
    equal = ca == cb
    w = weight(ca)
    duplicate = equal and w >= MIN_WEIGHT
    return {
        "card_a": ca,
        "card_b": cb,
        "cards_equal": equal,
        "weight": w,
        "min_weight": MIN_WEIGHT,
        "verdict": "DUPLICATE" if duplicate else "DISTINCT",
        "method": (
            "boolean mechanism-card equality with min weight "
            f"{MIN_WEIGHT}; scores are not an input"
        ),
    }
