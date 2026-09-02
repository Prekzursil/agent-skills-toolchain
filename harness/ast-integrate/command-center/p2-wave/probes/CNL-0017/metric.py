#!/usr/bin/env python3
"""Stakeholder-balance metric for CNL-0017.

Balance is L1/total-variation distance from a *declared* occupancy target,
not class richness, Shannon entropy, min-share, or max/min evenness.

I = (1/2) * sum_c |O[c] - T[c]|
balanced iff I <= I_star
"""
from __future__ import annotations

from collections import Counter
from typing import Any

TAXONOMY_ID = "CNL-0017.stakeholder.v1"

# Closed catalog: whose interest the seat represents. Not a CNL-0005 dial.
# Role = protocol function; stakeholder_class = interest-bearing party.
CLASSES: tuple[str, ...] = (
    "owner",
    "operator",
    "end_user",
    "implementer",
    "adversary",
    "compliance",
)

CLASS_INTEREST = {
    "owner": "authority to accept or reject the decision",
    "operator": "duty to run the result day to day",
    "end_user": "lives with the output; no implementation duty",
    "implementer": "must build or maintain the change",
    "adversary": "tasked to reject or break the proposal",
    "compliance": "policy or constraint bearer",
}

# CNL-0005 catalog question lists these nine per-seat dials. stakeholder_class
# is not among them. Artifact CNL-0005 is absent on this tree (NOT-CHECKED).
CNL_0005_NINE_DIALS = (
    "model",
    "vendor",
    "expertise",
    "role",
    "authority",
    "vote_weight",
    "tools",
    "effort",
    "context",
)


def census(seats: list[dict[str, Any]]) -> tuple[dict[str, int], list[str]]:
    counts = {c: 0 for c in CLASSES}
    unknown: list[str] = []
    for seat in seats:
        label = seat.get("stakeholder_class")
        sid = str(seat.get("id") or "?")
        if label not in counts:
            unknown.append(sid)
        else:
            counts[str(label)] += 1
    return counts, unknown


def imbalance(observed: dict[str, int], target: dict[str, int]) -> int:
    keys = set(CLASSES) | set(target) | set(observed)
    total = 0
    for key in keys:
        total += abs(int(observed.get(key, 0)) - int(target.get(key, 0)))
    if total % 2:
        raise ValueError(f"odd L1 mass {total}: seat count and target sum disagree")
    return total // 2


def richness(observed: dict[str, int]) -> int:
    return sum(1 for c in CLASSES if int(observed.get(c, 0)) > 0)


def unfilled(observed: dict[str, int], target: dict[str, int]) -> list[str]:
    return [
        c
        for c in CLASSES
        if int(target.get(c, 0)) > 0 and int(observed.get(c, 0)) == 0
    ]


def score(
    seats: list[dict[str, Any]],
    target: dict[str, int],
    i_star: int,
) -> dict[str, Any]:
    observed, unknown = census(seats)
    valid = not unknown
    I = imbalance(observed, target) if valid else None
    D = richness(observed)
    fires = (not valid) or (I is not None and I > i_star)
    return {
        "valid": valid,
        "unknown_seat_ids": unknown,
        "observed": observed,
        "target": {c: int(target.get(c, 0)) for c in CLASSES},
        "I": I,
        "D": D,
        "I_star": i_star,
        "unfilled": unfilled(observed, target) if valid else list(CLASSES),
        "fires": fires,
        "silent": valid and not fires,
        "n_seats": len(seats),
    }


def counter_census(seats: list[dict[str, Any]]) -> dict[str, int]:
    raw = Counter(str(s.get("stakeholder_class")) for s in seats)
    return {c: int(raw.get(c, 0)) for c in CLASSES}
