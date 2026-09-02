"""Named benchmarks for the variance-band pack (TST-0109).

Each benchmark times a real in-process workload; ``raw_for`` returns the
per-run vector (milliseconds) so every summary can be re-derived from it.
"""
from __future__ import annotations

import random
import time
from typing import Any, Callable

from variance_band.stats import EmptyInputError

__all__ = ["EmptyInputError", "router_once", "raw_for", "REQUIRED", "BENCHMARKS"]

REQUIRED = (
    "router-latency",
    "hook-overhead",
    "fan-out-throughput",
    "suite-wall-clock",
)

DEFAULT_REQUESTS = 200


def _default_requests(seed: int | None) -> list[dict[str, Any]]:
    rng = random.Random(seed if seed is not None else 109)
    return [{"id": i, "route": rng.choice(("a", "b", "c")), "weight": rng.random()} for i in range(DEFAULT_REQUESTS)]


def router_once(requests: list[dict[str, Any]] | None = None, *, seed: int | None = None) -> float:
    """Route one batch and return the elapsed wall-clock in milliseconds.

    An explicitly empty batch is refused: there is nothing to time, so no
    number is emitted (EmptyInputError) rather than a misleading 0.0.
    """
    if requests is None:
        requests = _default_requests(seed)
    if not requests:
        raise EmptyInputError("router_once: empty request batch")
    t0 = time.perf_counter()
    buckets: dict[str, float] = {}
    for req in requests:
        buckets[req.get("route", "?")] = buckets.get(req.get("route", "?"), 0.0) + float(req.get("weight", 1.0))
    _ = sorted(buckets.items())
    return (time.perf_counter() - t0) * 1000.0


def hook_once(requests: list[dict[str, Any]]) -> float:
    if not requests:
        raise EmptyInputError("hook_once: empty request batch")
    t0 = time.perf_counter()
    for req in requests:
        _ = dict(req)  # pre/post hook copies the envelope
    return (time.perf_counter() - t0) * 1000.0


def fan_out_once(requests: list[dict[str, Any]], width: int = 4) -> float:
    if not requests:
        raise EmptyInputError("fan_out_once: empty request batch")
    t0 = time.perf_counter()
    lanes: list[list[dict[str, Any]]] = [[] for _ in range(width)]
    for i, req in enumerate(requests):
        lanes[i % width].append(req)
    _ = [len(lane) for lane in lanes]
    return (time.perf_counter() - t0) * 1000.0


def suite_once(requests: list[dict[str, Any]]) -> float:
    if not requests:
        raise EmptyInputError("suite_once: empty request batch")
    t0 = time.perf_counter()
    router_once(requests)
    hook_once(requests)
    fan_out_once(requests)
    return (time.perf_counter() - t0) * 1000.0


BENCHMARKS: dict[str, tuple[Callable[[list[dict[str, Any]]], float], str]] = {
    "router-latency": (router_once, "ms/batch"),
    "hook-overhead": (hook_once, "ms/batch"),
    "fan-out-throughput": (fan_out_once, "ms/batch"),
    "suite-wall-clock": (suite_once, "ms/suite"),
}


def raw_for(bid: str, n: int = 8, seed: int | None = None, warmup: int = 1) -> list[float]:
    """Time benchmark ``bid`` ``n`` times on a seeded request batch."""
    if bid not in BENCHMARKS:
        raise KeyError(bid)
    fn, _metric = BENCHMARKS[bid]
    requests = _default_requests(seed)
    for _ in range(max(0, int(warmup))):
        fn(requests)  # warm-up runs, not recorded
    return [float(fn(requests)) for _ in range(int(n))]
