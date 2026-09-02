"""Named benchmarks for the variance-band pack."""
from __future__ import annotations

import time
from typing import Callable

from variance_band.stats import EmptyInputError

__all__ = ["EmptyInputError", "router_once", "raw_for", "REQUIRED"]

REQUIRED = (
    "router-latency",
    "hook-overhead",
    "fan-out-throughput",
    "suite-wall-clock",
)


def router_once() -> float:
    t0 = time.perf_counter()
    _ = sum(i * i for i in range(200))
    return (time.perf_counter() - t0) * 1000.0


def _series(fn: Callable[[], float], n: int = 8) -> list[float]:
    return [float(fn()) for _ in range(n)]


def raw_for(bid: str) -> list[float]:
    if bid == "router-latency":
        return _series(router_once)
    if bid == "hook-overhead":
        return _series(lambda: router_once() * 0.4)
    if bid == "fan-out-throughput":
        return _series(lambda: 12.0 + router_once() * 0.01)
    if bid == "suite-wall-clock":
        return _series(lambda: 40.0 + router_once() * 0.02)
    raise KeyError(bid)
