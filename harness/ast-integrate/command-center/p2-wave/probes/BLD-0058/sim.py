"""Discrete-time token-bucket vendor + arrival scheduler for BLD-0058.

Wall-clock sleeps are forbidden: 10x catalog fan-out is simulated in-process.
Live vendors are never contacted (retry_policy: never 429-storm a live vendor).
"""
from __future__ import annotations

from dataclasses import dataclass

MS_PER_MIN = 60_000
FIXTURE_RPM = 500
INTERACTIVE_RESERVE = 0.20
INTERACTIVE_SLA_MS = 2_000


def classify_status(http_status: int) -> str:
    if http_status == 429:
        return "OUR_ARRIVAL_RATE"
    if http_status == 529:
        return "VENDOR_OVERLOAD"
    if http_status == 200:
        return "OK"
    return "OTHER"


def scheduler_response(http_status: int) -> str:
    if http_status == 429:
        return "stagger-and-backoff; do-not-mark-unit-failed"
    if http_status == 529:
        return "keep-concurrency; do-not-self-throttle"
    return "continue"


def correct_adjust_concurrency(http_status: int, cap: int) -> int:
    """529/429 must not shrink the pool. 529 especially is vendor capacity."""
    _ = http_status
    return cap


def naive_adjust_concurrency(http_status: int, cap: int) -> int:
    """Negative control: the known-wrong response to vendor overload."""
    if http_status == 529:
        return max(1, cap - 1)
    return cap


class TokenBucket:
    def __init__(self, rpm: int, t_ms: int = 0) -> None:
        self.rpm = float(rpm)
        self.capacity = float(rpm)
        self.tokens = float(rpm)
        self.t_ms = t_ms

    def advance(self, t_ms: int) -> None:
        if t_ms < self.t_ms:
            raise ValueError("time went backwards")
        dt_min = (t_ms - self.t_ms) / MS_PER_MIN
        self.tokens = min(self.capacity, self.tokens + dt_min * self.rpm)
        self.t_ms = t_ms

    def try_take(self, t_ms: int) -> bool:
        self.advance(t_ms)
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


@dataclass
class FireResult:
    n: int
    n_200: int
    n_429: int
    n_529: int = 0
    first_429_index: int | None = None
    successes_at_t0: int = 0

    @property
    def has_429(self) -> bool:
        return self.n_429 > 0


def burst_times(n: int) -> list[int]:
    return [0] * n


def stagger_times(n: int, admit_rpm: float) -> list[int]:
    if admit_rpm <= 0:
        raise ValueError("admit_rpm must be positive")
    interval_ms = MS_PER_MIN / admit_rpm
    return [int(i * interval_ms) for i in range(n)]


def fire(
    times: list[int],
    rpm: int = FIXTURE_RPM,
    overload_at: int | None = None,
) -> FireResult:
    bucket = TokenBucket(rpm)
    n_200 = n_429 = n_529 = 0
    first_429: int | None = None
    successes_at_t0 = 0
    for i, t in enumerate(times):
        if overload_at is not None and i == overload_at:
            n_529 += 1
            continue
        if bucket.try_take(t):
            n_200 += 1
            if t == 0:
                successes_at_t0 += 1
        else:
            n_429 += 1
            if first_429 is None:
                first_429 = i
    return FireResult(
        n=len(times),
        n_200=n_200,
        n_429=n_429,
        n_529=n_529,
        first_429_index=first_429,
        successes_at_t0=successes_at_t0,
    )


def both_states_10x(n_10x: int, rpm: int = FIXTURE_RPM) -> dict:
    burst = fire(burst_times(n_10x), rpm=rpm)
    admit = rpm * (1.0 - INTERACTIVE_RESERVE)
    staggered = fire(stagger_times(n_10x, admit_rpm=admit), rpm=rpm)
    if not burst.has_429:
        raise AssertionError("vacuous both-states: burst produced zero 429s")
    if staggered.has_429:
        raise AssertionError(
            f"stagger still 429s: {staggered.n_429}/{staggered.n}"
        )
    return {
        "n_10x": n_10x,
        "rpm": rpm,
        "admit_rpm": admit,
        "burst_429": burst.n_429,
        "burst_200": burst.n_200,
        "stagger_429": staggered.n_429,
        "stagger_200": staggered.n_200,
        "vacuous": False,
    }


def fifo_wait_ms(jobs_ahead: int, rpm: int) -> float:
    if rpm <= 0:
        raise ValueError("rpm")
    return jobs_ahead / rpm * MS_PER_MIN


def starve_point(rpm: int = FIXTURE_RPM, sla_ms: int = INTERACTIVE_SLA_MS) -> dict:
    threshold = rpm * sla_ms / MS_PER_MIN
    pending = int(threshold) + 1
    wait = fifo_wait_ms(pending, rpm)
    return {
        "rpm": rpm,
        "sla_ms": sla_ms,
        "pending_jobs_that_break_sla": pending,
        "wait_ms_at_threshold": wait,
        "analytic": True,
    }


def interactive_behind_burst(n_batch: int, rpm: int = FIXTURE_RPM) -> dict:
    served_immediately = min(n_batch, rpm)
    queued = max(0, n_batch - served_immediately)
    wait = fifo_wait_ms(queued, rpm)
    return {
        "n_batch": n_batch,
        "served_at_t0": served_immediately,
        "queued_ahead_of_interactive": queued,
        "interactive_wait_ms": wait,
        "starves_sla": wait > INTERACTIVE_SLA_MS,
    }


def reserved_interactive_wait_ms() -> float:
    return 0.0


@dataclass
class OverloadTrial:
    cap_before: int
    cap_after_correct: int
    cap_after_naive: int
    status: int
    classification: str

    @property
    def correct_kept_cap(self) -> bool:
        return self.cap_after_correct == self.cap_before

    @property
    def naive_reduced_cap(self) -> bool:
        return self.cap_after_naive < self.cap_before


def overload_trial(cap: int = 8) -> OverloadTrial:
    status = 529
    return OverloadTrial(
        cap_before=cap,
        cap_after_correct=correct_adjust_concurrency(status, cap),
        cap_after_naive=naive_adjust_concurrency(status, cap),
        status=status,
        classification=classify_status(status),
    )
