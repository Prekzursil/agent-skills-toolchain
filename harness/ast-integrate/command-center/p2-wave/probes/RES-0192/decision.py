#!/usr/bin/env python3
"""Decision rule: RAPID vs SYSTEMATIC from four scored factors.

Scale for blast, density, contradiction: 0=low, 1=medium, 2=high.
Reversibility: 0=irreversible, 1=costly-to-reverse, 2=cheaply reversible.

SYSTEMATIC is required when any hard gate fires, or when the weighted
score is >= 6. Otherwise RAPID is allowed. This is a rule, not a
constant: Q1 (settled 27-item checklist) scores 0 and stays RAPID;
Q2 (irreversible high-blast contested methods) trips two hard gates.
"""
from __future__ import annotations

from typing import Any

WEIGHT_THRESHOLD = 6

# Mutant ids used by both-states probes. Never used in the live rule.
MUTANT_ALWAYS_SYSTEMATIC = "always-systematic"
MUTANT_ALWAYS_RAPID = "always-rapid"


def weighted_score(factors: dict[str, int]) -> int:
    rev = int(factors["reversibility"])
    blast = int(factors["blast"])
    density = int(factors["density"])
    contradiction = int(factors["contradiction"])
    return (2 - rev) + blast + density + contradiction


def hard_gates(factors: dict[str, int]) -> list[str]:
    rev = int(factors["reversibility"])
    blast = int(factors["blast"])
    density = int(factors["density"])
    contradiction = int(factors["contradiction"])
    fired: list[str] = []
    if rev <= 0 and blast >= 2:
        fired.append("irreversible-and-high-blast")
    if contradiction >= 2 and density >= 2:
        fired.append("high-contradiction-and-dense-literature")
    return fired


def recommend(factors: dict[str, int], mutant: str | None = None) -> dict[str, Any]:
    if mutant == MUTANT_ALWAYS_SYSTEMATIC:
        return {
            "protocol": "SYSTEMATIC",
            "mutant": mutant,
            "hard_gates": ["mutant-constant"],
            "weighted_score": weighted_score(factors),
            "threshold": WEIGHT_THRESHOLD,
            "reason": "mutant always-systematic (not the live rule)",
        }
    if mutant == MUTANT_ALWAYS_RAPID:
        return {
            "protocol": "RAPID",
            "mutant": mutant,
            "hard_gates": ["mutant-constant"],
            "weighted_score": weighted_score(factors),
            "threshold": WEIGHT_THRESHOLD,
            "reason": "mutant always-rapid (not the live rule)",
        }
    gates = hard_gates(factors)
    score = weighted_score(factors)
    if gates or score >= WEIGHT_THRESHOLD:
        protocol = "SYSTEMATIC"
        reason = (
            "hard gates: " + ",".join(gates)
            if gates
            else f"weighted_score {score} >= {WEIGHT_THRESHOLD}"
        )
    else:
        protocol = "RAPID"
        reason = f"no hard gate; weighted_score {score} < {WEIGHT_THRESHOLD}"
    return {
        "protocol": protocol,
        "mutant": None,
        "hard_gates": gates,
        "weighted_score": score,
        "threshold": WEIGHT_THRESHOLD,
        "reason": reason,
        "factors": dict(factors),
    }
