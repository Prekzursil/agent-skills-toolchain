"""Declared caps and two-leg consume plan for TST-0170.

Caps are declared up front. Leg sizes are chosen so every axis is partially
spent before suspend and again after resume, leaving a non-zero remainder.
"""
from __future__ import annotations

from copy import deepcopy

AXES = ("retries", "tokens", "wall_clock_ms")

# Declared cap (fresh-run full budget). Wall-clock is remaining-ms, not a clock.
CAPS = {
    "retries": 8,
    "tokens": 4000,
    "wall_clock_ms": 120000,
}

LEG1 = {
    "retries": 2,
    "tokens": 900,
    "wall_clock_ms": 35000,
}

LEG2 = {
    "retries": 1,
    "tokens": 1100,
    "wall_clock_ms": 20000,
}

RUN_ID = "tst-0170-two-leg"


def remaining_after(*legs: dict) -> dict[str, int]:
    left = deepcopy(CAPS)
    for leg in legs:
        for axis in AXES:
            left[axis] -= int(leg[axis])
            if left[axis] < 0:
                raise ValueError(f"plan-over-cap:{axis}")
    return left


def consumed_of(*legs: dict) -> dict[str, int]:
    total = {axis: 0 for axis in AXES}
    for leg in legs:
        for axis in AXES:
            total[axis] += int(leg[axis])
    return total


EXPECT_AFTER_LEG1 = remaining_after(LEG1)
EXPECT_AFTER_BOTH = remaining_after(LEG1, LEG2)
EXPECT_CONSUMED = consumed_of(LEG1, LEG2)
