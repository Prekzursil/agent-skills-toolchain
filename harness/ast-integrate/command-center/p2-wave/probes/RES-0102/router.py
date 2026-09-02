"""Deterministic component-aware lexical router.

Weights are declared here, before any gold-set score is computed. Ablating a
component zeroes that field's contribution. `irrelevant_meta` has weight 0 so
it is the designated control: routing must not consult it.
"""
from __future__ import annotations

from textutil import coverage, tokens

# Declared before measurement. Do not fit to a result.
WEIGHTS = {
    "trigger_phrases": 5.0,
    "examples": 2.5,
    "length_body": 0.20,
    "negative_scope": -6.0,
    "irrelevant_meta": 0.0,
}
ABSTAIN_MIN = 0.18
ABSTAIN = "ABSTAIN"


def score_skill(query: str, skill: dict) -> float:
    q = tokens(query)
    total = 0.0
    comps = skill["components"]
    for name, weight in WEIGHTS.items():
        if weight == 0.0:
            continue
        total += weight * coverage(q, tokens(comps.get(name, "")))
    return total


def route(query: str, skills: list[dict]) -> dict:
    ranked = []
    for skill in skills:
        s = score_skill(query, skill)
        ranked.append({"id": skill["id"], "score": round(s, 6)})
    ranked.sort(key=lambda r: (-r["score"], r["id"]))
    best = ranked[0] if ranked else {"id": ABSTAIN, "score": 0.0}
    chosen = best["id"] if best["score"] >= ABSTAIN_MIN else ABSTAIN
    return {
        "chosen": chosen,
        "best_score": best["score"],
        "abstained": chosen == ABSTAIN,
        "ranked": ranked[:5],
    }
