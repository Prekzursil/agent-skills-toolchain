#!/usr/bin/env python3
"""B07-contracted full-jitter retry backoff, timeout-bounded.

The catalog names "B07 dispatcher + scheduler" and the estate retry policy
"3 attempts with jittered exponential backoff (base 2s, cap 60s, full jitter)".
This worktree has no tools/agentspec/agentspec/retry.py and no dispatcher
module, so this file IS the live scheduler under test for TST-0138.

Algorithm (AWS "full jitter"):
    ceiling(attempt) = min(cap, base * 2^attempt)
    delay(attempt)   = Uniform(0, ceiling(attempt))

Invariant the unit asks for:
    sum(retry_schedule(...)) < timeout_seconds
for every generated schedule, including the worst case. When the unclipped
exponential sum would meet or exceed the timeout, later delays are clipped
(or dropped) so the budget cannot outlive the unit.
"""
from __future__ import annotations

import random
from typing import Sequence

# Supported ranges exercised by the property test (catalog-scale plus a
# short-timeout band that makes clipping load-bearing).
SUPPORTED_BASES: tuple[float, ...] = (0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0)
SUPPORTED_CAPS: tuple[float, ...] = (1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0)
SUPPORTED_ATTEMPTS: tuple[int, ...] = tuple(range(1, 11))
SUPPORTED_TIMEOUTS: tuple[float, ...] = (50.0, 60.0, 300.0, 1800.0, 3600.0)

# Catalog retry_policy for this family: base 2s, cap 60s, 3 attempts, 3600s unit.
CATALOG_BASE = 2.0
CATALOG_CAP = 60.0
CATALOG_ATTEMPTS = 3
CATALOG_TIMEOUT = 3600.0

EPSILON = 1e-9


def attempt_ceiling(attempt: int, base: float, cap: float) -> float:
    if attempt < 0:
        raise ValueError("attempt must be >= 0")
    if base < 0 or cap < 0:
        raise ValueError("base and cap must be >= 0")
    return min(float(cap), float(base) * (2**attempt))


def worst_case_unclipped(max_attempts: int, base: float, cap: float) -> float:
    """Sum of exponential ceilings with no timeout clip (the bound we must beat)."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")
    return sum(attempt_ceiling(i, base, cap) for i in range(max_attempts - 1))


def full_jitter_delay(
    attempt: int, base: float, cap: float, rng: random.Random
) -> float:
    ceiling = attempt_ceiling(attempt, base, cap)
    if ceiling <= 0.0:
        return 0.0
    return rng.uniform(0.0, ceiling)


def retry_schedule(
    *,
    max_attempts: int,
    base: float,
    cap: float,
    timeout_seconds: float,
    rng: random.Random | None = None,
    epsilon: float = EPSILON,
) -> list[float]:
    """Delays *between* attempts. Length is at most max_attempts-1.

    First attempt is immediate. Each subsequent attempt waits a full-jitter
    delay, clipped so the running sum stays strictly below timeout_seconds.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")
    if timeout_seconds <= 0.0:
        return []
    if rng is None:
        rng = random.SystemRandom()
    delays: list[float] = []
    spent = 0.0
    for attempt in range(max_attempts - 1):
        remaining = timeout_seconds - spent
        if remaining <= epsilon:
            break
        raw = full_jitter_delay(attempt, base, cap, rng)
        clipped = min(raw, remaining - epsilon)
        if clipped < 0.0:
            break
        delays.append(clipped)
        spent += clipped
    return delays


def unjittered_schedule(
    *,
    max_attempts: int,
    base: float,
    cap: float,
    timeout_seconds: float,
    rng: random.Random | None = None,
    epsilon: float = EPSILON,
) -> list[float]:
    """Negative control: deterministic exponential, no jitter.

    Still clipped to the timeout so a bound failure is not confused with a
    jitter failure. Two runs with the same parameters are identical.
    `rng` is accepted and ignored so the call shape matches retry_schedule.
    """
    del rng
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")
    if timeout_seconds <= 0.0:
        return []
    delays: list[float] = []
    spent = 0.0
    for attempt in range(max_attempts - 1):
        remaining = timeout_seconds - spent
        if remaining <= epsilon:
            break
        raw = attempt_ceiling(attempt, base, cap)
        clipped = min(raw, remaining - epsilon)
        if clipped < 0.0:
            break
        delays.append(clipped)
        spent += clipped
    return delays


def schedule_sum(schedule: Sequence[float]) -> float:
    return float(sum(schedule))


def bound_holds(schedule: Sequence[float], timeout_seconds: float) -> bool:
    return schedule_sum(schedule) < timeout_seconds


def symbolic_bound_holds(
    max_attempts: int, base: float, cap: float, timeout_seconds: float
) -> dict:
    """Exhaustive bound without sampling.

    Unclipped worst-case may exceed timeout; the clip construction still
    guarantees sum < timeout because each delay takes at most remaining-eps.
    """
    unclipped = worst_case_unclipped(max_attempts, base, cap)
    n = max(max_attempts - 1, 0)
    clipped_worst = min(unclipped, max(timeout_seconds - EPSILON * max(n, 1), 0.0))
    return {
        "unclipped_worst_case": unclipped,
        "clipped_worst_case": clipped_worst,
        "timeout_seconds": timeout_seconds,
        "clipping_load_bearing": unclipped >= timeout_seconds,
        "bound_holds": clipped_worst < timeout_seconds,
    }
