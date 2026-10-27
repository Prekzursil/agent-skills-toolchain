"""Arrival-rate scheduler: quota and refill are constructor inputs, not 429 outcomes.

IMP-0427. A naive burst against a capacity-limited fixture reproduces a 429
storm; the same unit count admitted through a token bucket does not.
Provider 529 retries without shrinking concurrency_cap. headroom_ok=False is
a local 503 with no vendor call.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Protocol

SENTINEL = "SENTINEL:IMP-0427:ARRIVAL-RATE-SCHEDULED"
MAX_TRANSIENT_ATTEMPTS = 3
DEFAULT_EPOCH = datetime(2026, 8, 24, 18, 0, 0, tzinfo=timezone.utc)
DEFAULT_CAPACITY = 8.0
DEFAULT_REFILL_PER_SEC = 8.0
DEFAULT_N_UNITS = 40
DEFAULT_529_UNITS = 16
DEFAULT_529_INJECT = 4


class Clock(Protocol):
    def now(self) -> float: ...
    def sleep(self, seconds: float) -> None: ...
    def datetime_now(self) -> datetime: ...


class FakeClock:
    """Deterministic clock. sleep() advances t; no wall wait."""

    def __init__(
        self,
        start: float = 0.0,
        epoch: datetime | None = None,
    ) -> None:
        self._t = float(start)
        self._epoch = epoch if epoch is not None else DEFAULT_EPOCH

    def now(self) -> float:
        return self._t

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            self._t += float(seconds)

    def datetime_now(self) -> datetime:
        return self._epoch + timedelta(seconds=self._t)


@dataclass
class SchedulerInputs:
    """Quota and arrival rate are scheduler inputs, not inferred from 429s."""

    arrival_rate_per_sec: float
    burst_capacity: float
    concurrency_cap: int
    default_backoff_sec: float = 1.0
    headroom_ok: bool = True
    max_transient_attempts: int = MAX_TRANSIENT_ATTEMPTS


@dataclass
class ProviderResponse:
    status: int
    retry_after: str | None
    unit_id: str
    t: float


class Provider(Protocol):
    def call(self, unit_id: str) -> ProviderResponse: ...


class TokenBucket:
    """Refilling bucket. try_consume is atomic: refuse leaves tokens unchanged."""

    def __init__(
        self,
        capacity: float,
        refill_per_sec: float,
        clock: FakeClock,
        initial: float | None = None,
    ) -> None:
        if capacity < 0:
            raise ValueError("capacity must be >= 0")
        self.capacity = float(capacity)
        self.refill_per_sec = float(refill_per_sec)
        self.clock = clock
        self._tokens = self.capacity if initial is None else float(initial)
        if self._tokens < 0:
            self._tokens = 0.0
        if self._tokens > self.capacity:
            self._tokens = self.capacity
        self._last = clock.now()

    def _refill(self) -> None:
        now = self.clock.now()
        elapsed = now - self._last
        if elapsed > 0 and self.refill_per_sec > 0:
            self._tokens = min(
                self.capacity,
                self._tokens + elapsed * self.refill_per_sec,
            )
        self._last = now
        if self._tokens < 0:
            self._tokens = 0.0
        if self._tokens > self.capacity:
            self._tokens = self.capacity

    @property
    def tokens(self) -> float:
        self._refill()
        return self._tokens

    def try_consume(self, n: float = 1.0) -> bool:
        if n <= 0:
            return False
        self._refill()
        if self._tokens + 1e-12 < n:
            return False
        self._tokens -= float(n)
        if self._tokens < 0:
            self._tokens = 0.0
        return True

    def time_until(self, n: float = 1.0) -> float:
        self._refill()
        if self._tokens + 1e-12 >= n:
            return 0.0
        if self.refill_per_sec <= 0:
            return float("inf")
        return (n - self._tokens) / self.refill_per_sec

    def acquire(self, n: float = 1.0) -> bool:
        wait = self.time_until(n)
        if wait > 0 and wait != float("inf"):
            self.clock.sleep(wait)
        return self.try_consume(n)


def token_bucket_checks() -> list[tuple[str, bool, str]]:
    """Named invariants consumed by probe 1. Details are load-bearing strings."""
    checks: list[tuple[str, bool, str]] = []

    clock = FakeClock()
    b = TokenBucket(8.0, 8.0, clock)
    checks.append(
        ("starts_at_capacity", abs(b.tokens - 8.0) < 1e-9, f"tokens={b.tokens}")
    )

    b.try_consume(3.0)
    checks.append(
        ("consume_reduces", abs(b.tokens - 5.0) < 1e-9, f"tokens={b.tokens}")
    )

    empty = TokenBucket(8.0, 8.0, FakeClock(), initial=0.0)
    got = empty.try_consume(1.0)
    checks.append(
        (
            "empty_does_not_go_negative",
            (not got) and empty.tokens == 0.0,
            f"failed={got} tokens={empty.tokens}",
        )
    )

    over = TokenBucket(8.0, 8.0, FakeClock(), initial=2.0)
    over.try_consume(3.0)
    checks.append(
        (
            "refuse_oversize_atomic",
            abs(over.tokens - 2.0) < 1e-9,
            f"tokens={over.tokens}",
        )
    )

    c4 = FakeClock()
    r = TokenBucket(8.0, 8.0, c4, initial=0.0)
    c4.sleep(0.125)
    checks.append(
        (
            "refill_rate_exact",
            abs(r.tokens - 1.0) < 1e-9,
            f"tokens_after_0.125s={r.tokens}",
        )
    )

    got2 = r.try_consume(1.0)
    checks.append(
        (
            "refill_then_consume",
            got2 and abs(r.tokens) < 1e-9,
            f"got={got2} leftover={r.tokens}",
        )
    )

    c5 = FakeClock()
    cap = TokenBucket(4.0, 8.0, c5, initial=4.0)
    c5.sleep(10.0)
    checks.append(
        (
            "never_above_capacity",
            abs(cap.tokens - 4.0) < 1e-9,
            f"tokens={cap.tokens}",
        )
    )

    t = TokenBucket(8.0, 8.0, FakeClock(), initial=0.0)
    wait = t.time_until(1.0)
    checks.append(
        ("time_until_empty", abs(wait - 0.125) < 1e-9, f"wait={wait}")
    )

    drain = TokenBucket(5.0, 0.0, FakeClock(), initial=5.0)
    while drain.try_consume(1.0):
        pass
    drain.try_consume(1.0)
    ok = drain.tokens >= 0.0
    checks.append(
        ("tokens_never_negative_after_drain", ok, "ok" if ok else f"tokens={drain.tokens}")
    )
    return checks


def retry_wait_seconds(
    header: str | None,
    clock: FakeClock,
    fallback: float,
) -> float:
    """Honor Retry-After (delta-seconds or HTTP-date). Malformed → fallback."""
    if header is None:
        return max(0.0, float(fallback))
    text = str(header).strip()
    if not text:
        return max(0.0, float(fallback))
    try:
        n = int(text)
        return float(max(0, n))
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        wait = (dt - clock.datetime_now()).total_seconds()
        return max(0.0, wait)
    except (TypeError, ValueError, OverflowError):
        return max(0.0, float(fallback))


class FixtureProvider:
    """Capacity-limited fixture. 429 when the caller outruns the bucket."""

    def __init__(
        self,
        clock: FakeClock,
        capacity: float = DEFAULT_CAPACITY,
        refill_per_sec: float = DEFAULT_REFILL_PER_SEC,
        inject_529: list[str] | None = None,
    ) -> None:
        self.clock = clock
        self.bucket = TokenBucket(capacity, refill_per_sec, clock)
        self._inject = set(inject_529 or [])
        self._seen_529: set[str] = set()
        self.n_200 = 0
        self.n_429 = 0
        self.n_529 = 0
        self.calls: list[ProviderResponse] = []
        self.n_calls = 0

    def call(self, unit_id: str) -> ProviderResponse:
        t = self.clock.now()
        self.n_calls += 1
        if unit_id in self._inject and unit_id not in self._seen_529:
            self._seen_529.add(unit_id)
            self.n_529 += 1
            resp = ProviderResponse(status=529, retry_after=None, unit_id=unit_id, t=t)
            self.calls.append(resp)
            return resp
        if self.bucket.try_consume(1.0):
            self.n_200 += 1
            resp = ProviderResponse(status=200, retry_after=None, unit_id=unit_id, t=t)
            self.calls.append(resp)
            return resp
        self.n_429 += 1
        resp = ProviderResponse(status=429, retry_after=None, unit_id=unit_id, t=t)
        self.calls.append(resp)
        return resp


@dataclass
class ArmResult:
    arm: str
    concurrency_cap_after: int
    concurrency_cap_before: int
    elapsed_fake_sec: float
    n_200: int
    n_429: int
    n_529: int
    n_terminal_fail: int
    n_terminal_ok: int
    n_units: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "arm": self.arm,
            "concurrency_cap_after": self.concurrency_cap_after,
            "concurrency_cap_before": self.concurrency_cap_before,
            "elapsed_fake_sec": self.elapsed_fake_sec,
            "n_200": self.n_200,
            "n_429": self.n_429,
            "n_529": self.n_529,
            "n_terminal_fail": self.n_terminal_fail,
            "n_terminal_ok": self.n_terminal_ok,
            "n_units": self.n_units,
        }


@dataclass
class BothStates:
    burst: ArmResult
    scheduled: ArmResult
    capacity: float
    refill_per_sec: float
    n_units: int
    load_escalations: int
    vacuous: bool

    @property
    def burst_is_real_control(self) -> bool:
        return self.burst.n_429 > 0

    @property
    def scheduler_avoids_storm(self) -> bool:
        return self.scheduled.n_429 == 0

    @property
    def identical_unit_count(self) -> bool:
        return self.burst.n_units == self.scheduled.n_units == self.n_units

    def ok(self) -> bool:
        return (
            self.identical_unit_count
            and self.burst_is_real_control
            and self.scheduler_avoids_storm
            and not self.vacuous
        )


def both_states_to_dict(cmp: BothStates) -> dict[str, Any]:
    return {
        "burst": cmp.burst.as_dict(),
        "burst_is_real_control": cmp.burst_is_real_control,
        "capacity": cmp.capacity,
        "identical_unit_count": cmp.identical_unit_count,
        "load_escalations": cmp.load_escalations,
        "n_units": cmp.n_units,
        "ok": cmp.ok(),
        "refill_per_sec": cmp.refill_per_sec,
        "scheduled": cmp.scheduled.as_dict(),
        "scheduler_avoids_storm": cmp.scheduler_avoids_storm,
        "vacuous": cmp.vacuous,
    }


def dispatch_scheduled(
    unit_ids: list[str],
    provider: Provider,
    inputs: SchedulerInputs,
    clock: FakeClock,
) -> list[ProviderResponse]:
    """Staggered admission. Retries 429/529; never lowers concurrency_cap."""
    return _dispatch(unit_ids, provider, inputs, clock, stagger=True)


def dispatch_burst(
    unit_ids: list[str],
    provider: Provider,
    inputs: SchedulerInputs,
    clock: FakeClock,
) -> list[ProviderResponse]:
    """Naive herd: no token wait, no backoff sleep, immediate 429 retry."""
    return _dispatch(unit_ids, provider, inputs, clock, stagger=False)


def _dispatch(
    unit_ids: list[str],
    provider: Provider,
    inputs: SchedulerInputs,
    clock: FakeClock,
    *,
    stagger: bool,
) -> list[ProviderResponse]:
    terminals: list[ProviderResponse] = []
    if not inputs.headroom_ok:
        t = clock.now()
        for uid in unit_ids:
            terminals.append(
                ProviderResponse(status=503, retry_after=None, unit_id=uid, t=t)
            )
        return terminals

    bucket = TokenBucket(inputs.burst_capacity, inputs.arrival_rate_per_sec, clock)
    attempts = max(1, int(inputs.max_transient_attempts))
    # concurrency_cap is an input. 529 must not write a smaller value.
    _cap = int(inputs.concurrency_cap)
    for uid in unit_ids:
        if stagger:
            if not bucket.acquire(1.0):
                t = clock.now()
                terminals.append(
                    ProviderResponse(status=429, retry_after=None, unit_id=uid, t=t)
                )
                continue
        last: ProviderResponse | None = None
        terminal: ProviderResponse | None = None
        for _attempt in range(attempts):
            resp = provider.call(uid)
            last = resp
            if resp.status == 200:
                terminal = resp
                break
            if resp.status in (429, 529):
                if stagger:
                    wait = retry_wait_seconds(
                        resp.retry_after, clock, inputs.default_backoff_sec
                    )
                    clock.sleep(wait)
                # Do not reduce _cap on 529 (or 429).
                assert _cap == int(inputs.concurrency_cap)
                continue
            terminal = resp
            break
        terminals.append(terminal if terminal is not None else last)  # type: ignore[arg-type]
    return terminals


def _arm_from_dispatch(
    arm: str,
    unit_ids: list[str],
    provider: FixtureProvider,
    inputs: SchedulerInputs,
    clock: FakeClock,
    terminals: list[ProviderResponse],
    t0: float,
) -> ArmResult:
    n_ok = sum(1 for r in terminals if r is not None and r.status == 200)
    n_fail = len(unit_ids) - n_ok
    return ArmResult(
        arm=arm,
        concurrency_cap_after=int(inputs.concurrency_cap),
        concurrency_cap_before=int(inputs.concurrency_cap),
        elapsed_fake_sec=clock.now() - t0,
        n_200=provider.n_200,
        n_429=provider.n_429,
        n_529=provider.n_529,
        n_terminal_fail=n_fail,
        n_terminal_ok=n_ok,
        n_units=len(unit_ids),
    )


def _run_arm(
    arm: str,
    n_units: int,
    capacity: float,
    refill_per_sec: float,
) -> ArmResult:
    clock = FakeClock()
    ids = [f"u{i}" for i in range(n_units)]
    provider = FixtureProvider(clock, capacity=capacity, refill_per_sec=refill_per_sec)
    inputs = SchedulerInputs(
        arrival_rate_per_sec=refill_per_sec,
        burst_capacity=capacity,
        concurrency_cap=int(capacity),
        default_backoff_sec=0.0,
    )
    t0 = clock.now()
    if arm == "burst":
        terminals = dispatch_burst(ids, provider, inputs, clock)
    else:
        terminals = dispatch_scheduled(ids, provider, inputs, clock)
    return _arm_from_dispatch(arm, ids, provider, inputs, clock, terminals, t0)


def run_both_states(
    n_units: int = DEFAULT_N_UNITS,
    capacity: float = DEFAULT_CAPACITY,
    refill_per_sec: float = DEFAULT_REFILL_PER_SEC,
    max_escalations: int = 4,
) -> BothStates:
    """Burst versus scheduled at identical N. Escalate N if the burst is vacuous."""
    n = int(n_units)
    escalations = 0
    burst: ArmResult | None = None
    scheduled: ArmResult | None = None
    while True:
        burst = _run_arm("burst", n, capacity, refill_per_sec)
        scheduled = _run_arm("scheduled", n, capacity, refill_per_sec)
        vacuous = burst.n_429 == 0
        if not vacuous or escalations >= max_escalations:
            break
        n *= 2
        escalations += 1
    assert burst is not None and scheduled is not None
    vacuous = burst.n_429 == 0
    return BothStates(
        burst=burst,
        scheduled=scheduled,
        capacity=float(capacity),
        refill_per_sec=float(refill_per_sec),
        n_units=n,
        load_escalations=escalations,
        vacuous=vacuous,
    )


def run_529_concurrency_control(
    n_units: int = DEFAULT_529_UNITS,
    n_inject: int = DEFAULT_529_INJECT,
    capacity: float = DEFAULT_CAPACITY,
    refill_per_sec: float = DEFAULT_REFILL_PER_SEC,
) -> dict[str, Any]:
    """Injected 529s retry to completion; concurrency_cap is unchanged."""
    clock = FakeClock()
    ids = [f"u{i}" for i in range(n_units)]
    inject = ids[: int(n_inject)]
    provider = FixtureProvider(
        clock,
        capacity=capacity,
        refill_per_sec=refill_per_sec,
        inject_529=inject,
    )
    cap = int(capacity)
    inputs = SchedulerInputs(
        arrival_rate_per_sec=refill_per_sec,
        burst_capacity=capacity,
        concurrency_cap=cap,
        default_backoff_sec=0.0,
    )
    cap_before = inputs.concurrency_cap
    terminals = dispatch_scheduled(ids, provider, inputs, clock)
    cap_after = inputs.concurrency_cap
    n_ok = sum(1 for r in terminals if r.status == 200)
    return {
        "all_succeeded": n_ok == n_units and len(terminals) == n_units,
        "concurrency_cap_after": cap_after,
        "concurrency_cap_before": cap_before,
        "concurrency_unchanged": cap_before == cap_after == cap,
        "n_429_observed": provider.n_429,
        "n_529_injected": len(inject),
        "n_529_observed": provider.n_529,
        "n_terminal_ok": n_ok,
        "n_units": n_units,
    }


@dataclass
class HeadroomProbe:
    called: list[str] = field(default_factory=list)

    def call(self, unit_id: str) -> ProviderResponse:
        self.called.append(unit_id)
        raise AssertionError("vendor must not be called when headroom_ok is False")


def headroom_refuses() -> dict[str, Any]:
    clock = FakeClock()
    provider = HeadroomProbe()
    inputs = SchedulerInputs(
        arrival_rate_per_sec=8.0,
        burst_capacity=8.0,
        concurrency_cap=8,
        headroom_ok=False,
    )
    terminals = dispatch_scheduled(["u0", "u1"], provider, inputs, clock)
    return {
        "n_vendor_calls": len(provider.called),
        "statuses": [r.status for r in terminals],
        "all_503": all(r.status == 503 for r in terminals),
    }
