"""A deterministic, injectable clock.

Every liveness, expiry and TTL decision in this package takes its time from a :data:`Clock`
supplied by the caller. Nothing reaches for ``time.time()`` inside a decision function. Wall clock
in a test is the non-determinism that makes an expiry assertion flaky, and a flaky assertion gets
deleted rather than fixed - so the clock is a parameter, and this is the double.

Not test-only: a caller that wants to REPLAY a coordination journal, or simulate a lease timeline,
needs exactly this. It lives in the package rather than in ``conftest.py`` so both the suite and a
simulation can import it by a stable name.
"""

from __future__ import annotations

__all__ = ["SimClock"]


class SimClock:
    """Advances only when told to. Callable, so it satisfies ``store.Clock`` directly."""

    def __init__(self, start: float = 1_700_000_000.0) -> None:
        self.now = float(start)

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> float:
        """Move forward. Never backwards: a clock that can go back is not a clock."""
        if seconds < 0:
            raise ValueError(f"refusing to move a clock backwards by {seconds}s")
        self.now += float(seconds)
        return self.now
