"""Synthetic rails for IMP-0221 quota/backoff probes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agentspec.retry import RATE_LIMITED_BACKOFF_CAP_MS


@dataclass
class RailResult:
    unit_id: str
    status: str
    wait_ms: int = 0
    retry_after_s: float = 0.0
    attempts: int = 1


class HealthyRail:
    def __init__(self, clock: Any) -> None:
        self.clock = clock

    def admit(self, unit_id: str, *, attempt: int = 1) -> RailResult:
        self.clock.advance(25)
        return RailResult(unit_id=unit_id, status="completed", attempts=attempt)


class TokenBucketRail:
    def __init__(
        self,
        *,
        capacity: float,
        refill_per_s: float,
        clock: Any,
        retry_after_s: float = 1.0,
    ) -> None:
        self.capacity = float(capacity)
        self.refill_per_s = float(refill_per_s)
        self.clock = clock
        self.retry_after_s = float(retry_after_s)
        self._tokens = float(capacity)
        self._last_ms = int(clock.now_ms())

    def _refill(self) -> None:
        now = int(self.clock.now_ms())
        elapsed_s = max(0, now - self._last_ms) / 1000.0
        self._tokens = min(self.capacity, self._tokens + elapsed_s * self.refill_per_s)
        self._last_ms = now

    def admit(self, unit_id: str, *, attempt: int = 1) -> RailResult:
        self._refill()
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            self.clock.advance(25)
            return RailResult(unit_id=unit_id, status="completed", attempts=attempt)
        wait_ms = int(self.retry_after_s * 1000)
        return RailResult(
            unit_id=unit_id,
            status="rate-limited",
            wait_ms=wait_ms,
            retry_after_s=self.retry_after_s,
            attempts=attempt,
        )


class Always429Rail:
    def __init__(self, clock: Any, retry_after_s: float = 2.0, huge: bool = False) -> None:
        self.clock = clock
        self.retry_after_s = 10_000.0 if huge else float(retry_after_s)
        self.huge = huge

    def admit(self, unit_id: str, *, attempt: int = 1) -> RailResult:
        wait_ms = min(int(self.retry_after_s * 1000), RATE_LIMITED_BACKOFF_CAP_MS)
        return RailResult(
            unit_id=unit_id,
            status="rate-limited",
            wait_ms=wait_ms,
            retry_after_s=self.retry_after_s,
            attempts=attempt,
        )


class OverloadRail:
    def __init__(self, clock: Any) -> None:
        self.clock = clock

    def admit(self, unit_id: str, *, attempt: int = 1) -> RailResult:
        self.clock.advance(10)
        return RailResult(unit_id=unit_id, status="overload", attempts=attempt)
