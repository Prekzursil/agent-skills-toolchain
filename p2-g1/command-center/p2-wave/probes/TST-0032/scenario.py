#!/usr/bin/env python3
"""TST-0032 planted control suite: the four behaviour classes.

Outcomes are seeded and deterministic so the N=20 repetition matrix is
reproducible: always_pass 20/20, coin_flip 10/20, rare_flake 19/20,
always_fail 0/20.
"""
from __future__ import annotations

import random
from typing import Callable

COIN_SEED = 12
RARE_SEED = 3


def _always_pass(run_index: int) -> None:
    return None


def _always_fail(run_index: int) -> None:
    raise AssertionError("planned failure (BROKEN class)")


def _coin_flip(run_index: int) -> None:
    rng = random.Random(COIN_SEED)
    for _ in range(run_index + 1):
        draw = rng.random()
    if draw < 0.5:
        raise AssertionError("coin came up tails (FLAKY class)")


def _rare_flake(run_index: int) -> None:
    rng = random.Random(RARE_SEED)
    for _ in range(run_index + 1):
        draw = rng.random()
    if draw < 0.05:
        raise AssertionError("rare tail (FLAKY class)")


def build_suite() -> list[tuple[str, Callable[[], None]]]:
    """Ordered suite; each callable takes the 0-based repetition index."""
    return [
        ("planted.always_pass", _always_pass),
        ("planted.coin_flip", _coin_flip),
        ("planted.rare_flake", _rare_flake),
        ("planted.always_fail", _always_fail),
    ]


EXPECTED_RATIOS = {
    "planted.always_pass": 1.0,
    "planted.coin_flip": 0.5,
    "planted.rare_flake": 0.95,
    "planted.always_fail": 0.0,
}
EXPECTED_CLASSES = {
    "planted.always_pass": "DETERMINISTIC",
    "planted.coin_flip": "FLAKY",
    "planted.rare_flake": "FLAKY",
    "planted.always_fail": "BROKEN",
}
EXPECTED_QUARANTINED = ["planted.coin_flip", "planted.rare_flake"]
