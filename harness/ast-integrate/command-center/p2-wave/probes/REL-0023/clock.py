#!/usr/bin/env python3
"""Named clock for REL-0023 exposure-window measurement.

The catalog forbids an estimated window. Every delay in this drill is the
difference of two samples from linux CLOCK_MONOTONIC via clock_gettime_ns.
"""
from __future__ import annotations

import time

CLOCK_SOURCE = "linux:CLOCK_MONOTONIC"
CLOCK_API = "time.clock_gettime_ns(time.CLOCK_MONOTONIC)"


class NamedClock:
    """Monotonic nanosecond clock with a stable published name."""

    name = CLOCK_SOURCE
    api = CLOCK_API

    def now_ns(self) -> int:
        return time.clock_gettime_ns(time.CLOCK_MONOTONIC)

    def sleep_s(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("sleep must be non-negative")
        time.sleep(seconds)


def delay_seconds(start_ns: int, end_ns: int) -> float:
    if end_ns < start_ns:
        raise ValueError("clock went backwards")
    return (end_ns - start_ns) / 1_000_000_000
