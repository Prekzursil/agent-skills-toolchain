"""Soak resource curve with planted leak (IMP-0242)."""
from __future__ import annotations

from typing import Any


class PerRunSoakTuneError(RuntimeError):
    pass


class LeakyWorkload:
    def sample(self, i: int) -> int:
        return 1000 + i * 40


class StableWorkload:
    def sample(self, i: int) -> int:
        return 1000 + (i % 3)


def load_soak_spec() -> dict[str, Any]:
    return {"duration_ms": 80, "samples": 8, "min_samples": 5, "adjective": None}


def run_soak(workload: Any, spec: dict[str, Any] | None = None) -> dict[str, Any]:
    spec = spec or load_soak_spec()
    n = int(spec.get("samples") or 8)
    curve = [int(workload.sample(i)) for i in range(n)]
    leak = curve[-1] - curve[0] > 50
    return {
        "verdict": "LEAK" if leak else "NO-LEAK",
        "leak_detected": leak,
        "retained_bytes": curve,
        "duration_declared_ms": int(spec["duration_ms"]),
        "adjective_verdict": None,
        "n": n,
        "min_samples": int(spec.get("min_samples") or 5),
        "sample_count": n,
    }
