#!/usr/bin/env python3
"""Planted suite for TST-0336. Deterministic, not SystemRandom.

The catalog control is a coin-flip test. A live RNG can theoretically come up
all-heads in 20 tosses and miss the quarantine assertion, so the coin-flip is
an alternating first-attempt pass/fail that still fails on retry-attempt 0 and
passes on retry — proving both detection and retry-absorption without luck.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Callable

COMMIT_SEED = "TST-0336-fixture-commit"
FIXED_NOW = datetime(2026, 8, 24, 18, 0, 0, tzinfo=timezone.utc)


def commit_sha() -> str:
    return hashlib.sha256(COMMIT_SEED.encode("utf-8")).hexdigest()


def stable_pass(*, run_index: int, attempt: int = 0) -> bool:
    return True


def broken_always(*, run_index: int, attempt: int = 0) -> bool:
    return False


def coin_flip(*, run_index: int, attempt: int = 0) -> bool:
    """50% first-attempt failures; any retry succeeds (the absorption bait)."""
    if attempt > 0:
        return True
    return (run_index % 2) == 0


def at_threshold(*, run_index: int, attempt: int = 0) -> bool:
    """Exactly 1 fail in 20: rate == 1/20, not *above*, so not quarantined."""
    return run_index != 7


def just_above(*, run_index: int, attempt: int = 0) -> bool:
    """2 fails in 20: rate 0.10 > 1/20, quarantined."""
    return run_index not in (3, 11)


def retry_bait(*, run_index: int, attempt: int = 0) -> bool:
    """Fails attempt 0 every run, passes on retry. Looks BROKEN honestly,
    looks green if retries are absorbed."""
    return attempt > 0


TESTS: dict[str, Callable[..., bool]] = {
    "stable_pass": stable_pass,
    "broken_always": broken_always,
    "coin_flip": coin_flip,
    "at_threshold": at_threshold,
    "just_above": just_above,
    "retry_bait": retry_bait,
}

REGISTRY: dict[str, dict[str, Any]] = {
    "stable_pass": {"owner": None},
    "broken_always": {"owner": "platform-ci"},
    "coin_flip": {
        "owner": "test-governance",
        "quarantine_opened_at": "2026-07-01T00:00:00Z",
        "deadline": "2026-09-01T00:00:00Z",
    },
    "at_threshold": {"owner": "test-governance"},
    "just_above": {
        "owner": "test-governance",
        "quarantine_opened_at": "2026-08-01T00:00:00Z",
        "deadline": "2026-08-31T00:00:00Z",
    },
    "retry_bait": {"owner": "test-governance"},
}


def tests_without(name: str) -> dict[str, Callable[..., bool]]:
    return {k: v for k, v in TESTS.items() if k != name}
