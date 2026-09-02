"""Injected clock for freshness windows."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


class Clock:
    def __init__(self, now: datetime | None = None) -> None:
        self._now = now or datetime.now(timezone.utc)

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> datetime:
        self._now = self._now + delta
        return self._now
