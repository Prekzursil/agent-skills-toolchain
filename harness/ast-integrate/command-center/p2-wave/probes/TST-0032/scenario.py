"""Planted suite for TST-0032. Same order every repetition.

Coin-flip fails on odd invocations so the 20th (last) run PASSES. A
green claim that still includes it must be blocked anyway.
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIB = REPO / "command-center" / "lib"

import sys

if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from flake_quarantine.ledger import (  # noqa: E402
    measure,
    ordered_suite,
    worktree_fingerprint,
)

ALWAYS_PASS = "planted.always_pass"
COIN_FLIP = "planted.coin_flip"
RARE_FLAKE = "planted.rare_flake"
ALWAYS_FAIL = "planted.always_fail"
ORDER = (ALWAYS_PASS, COIN_FLIP, RARE_FLAKE, ALWAYS_FAIL)
N = 20
RARE_FAIL_AT = 7


def always_pass() -> None:
    return None


def always_fail() -> None:
    raise AssertionError("planted broken")


class CoinFlip:
    """Deterministic 50/50 plant. Fail on odd 1-based invocations."""

    def __init__(self) -> None:
        self.invocations = 0

    def __call__(self) -> None:
        self.invocations += 1
        if self.invocations % 2 == 1:
            raise AssertionError("planted coin-flip fail")


class RareFlake:
    """Fails exactly once in N (0-based index RARE_FAIL_AT)."""

    def __init__(self, fail_at: int = RARE_FAIL_AT) -> None:
        self.invocations = 0
        self.fail_at = fail_at

    def __call__(self) -> None:
        idx = self.invocations
        self.invocations += 1
        if idx == self.fail_at:
            raise AssertionError(f"planted rare flake at repetition {idx}")


def fingerprint_paths() -> list[Path]:
    return [
        REPO / "command-center" / "lib" / "flake_quarantine" / "ledger.py",
        HERE / "scenario.py",
        HERE / "probe1_planted_coin_flip.py",
        HERE / "probe2_green_claim_blocked.py",
    ]


def build_suite():
    return ordered_suite(
        [
            (ALWAYS_PASS, always_pass),
            (COIN_FLIP, CoinFlip()),
            (RARE_FLAKE, RareFlake()),
            (ALWAYS_FAIL, always_fail),
        ]
    )


def run_planted(*, n: int = N, hypothesis: str | None = None, prior=None) -> dict:
    suite = build_suite()
    fp = worktree_fingerprint(fingerprint_paths())
    return measure(
        suite,
        n=n,
        fingerprint=fp,
        order=ORDER,
        hypothesis=hypothesis,
        prior=prior,
    )
