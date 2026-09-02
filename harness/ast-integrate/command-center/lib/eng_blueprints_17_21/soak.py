"""Concurrency-load-soak resource curve with planted leak (IMP-0242).

The soak spec is declared data (an integer duration in ms, a sample count and
a leak threshold in bytes), never an adjective, and never tuned per run. The
result of a soak is a *curve* of ``retained_bytes`` samples; a leak is a growth
across the curve above the declared threshold.
"""
from __future__ import annotations

import time
from typing import Any

SOAK_SPEC_ID = "imp-0242-soak-v1"

# Frozen, library-owned spec. ``duration_ms`` is the declared soak length,
# ``samples`` how many retained-bytes samples are taken across it.
_SOAK_SPEC: dict[str, Any] = {
    "id": SOAK_SPEC_ID,
    "version": "1.0.0",
    "duration_ms": 80,
    "samples": 16,
    "min_samples": 12,
    "leak_threshold_bytes": 256,
    "adjective": None,
    "frozen": True,
    "not_tuned_per_run": True,
}


class PerRunSoakTuneError(RuntimeError):
    """Raised when a caller tries to override the frozen soak spec for one run."""


class LeakyWorkload:
    """Planted retainer: every iteration keeps a fresh buffer alive."""

    def __init__(self, chunk: int = 64) -> None:
        self.chunk = chunk
        self._retained: list[bytes] = []

    def step(self, i: int) -> None:
        self._retained.append(bytes(self.chunk))

    def retained_bytes(self) -> int:
        return sum(len(b) for b in self._retained)


class StableWorkload:
    """Bounded working set: a ring of fixed size, so retention plateaus."""

    def __init__(self, ring: int = 4, chunk: int = 64) -> None:
        self.ring = ring
        self.chunk = chunk
        self._retained: list[bytes] = []

    def step(self, i: int) -> None:
        self._retained.append(bytes(self.chunk))
        if len(self._retained) > self.ring:
            self._retained.pop(0)

    def retained_bytes(self) -> int:
        return sum(len(b) for b in self._retained)


def load_soak_spec(spec_override: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return the frozen soak spec; any per-run override is refused."""
    if spec_override:
        raise PerRunSoakTuneError(
            f"soak spec {SOAK_SPEC_ID} is frozen; per-run override refused: "
            f"{sorted(spec_override)}"
        )
    return dict(_SOAK_SPEC)


def run_soak(workload: Any, spec: dict[str, Any] | None = None) -> dict[str, Any]:
    """Drive ``workload`` for the declared duration, sampling retained bytes.

    ``workload`` exposes ``step(i)`` and ``retained_bytes()``. The soak is
    time-boxed by ``duration_ms``: steps are paced so ``samples`` samples fall
    across the declared window; the observed wall time is reported alongside.
    """
    spec = dict(spec or load_soak_spec())
    n = int(spec["samples"])
    duration_ms = int(spec["duration_ms"])
    threshold = int(spec["leak_threshold_bytes"])
    pace_s = (duration_ms / 1000.0) / max(1, n)
    curve: list[dict[str, int]] = []
    start = time.perf_counter()
    for i in range(n):
        workload.step(i)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        curve.append(
            {"sample": i, "t_ms": elapsed_ms, "retained_bytes": int(workload.retained_bytes())}
        )
        if pace_s > 0 and i < n - 1:
            time.sleep(pace_s)
    observed_ms = int((time.perf_counter() - start) * 1000)
    growth = curve[-1]["retained_bytes"] - curve[0]["retained_bytes"]
    leak = growth > threshold
    return {
        "spec_id": spec["id"],
        "verdict": "LEAK" if leak else "NO-LEAK",
        "leak_detected": leak,
        "leak_growth_bytes": growth,
        "leak_threshold_bytes": threshold,
        "curve": curve,
        "retained_bytes": [pt["retained_bytes"] for pt in curve],
        "duration_declared_ms": duration_ms,
        "duration_observed_ms": observed_ms,
        "adjective_verdict": None,
        "n": n,
        "min_samples": int(spec["min_samples"]),
        "sample_count": len(curve),
    }
