"""Interval arithmetic for CNF-0027.

Quantile method (documented so a second reviewer can recompute):
  index = (n - 1) * p
  linear interpolation between floor(index) and ceil(index).
Median is p=0.5; IQR is Q3-Q1; noise floor is IQR (same units as the samples).
A claimed |delta| <= noise floor is UNMEASURABLE.
"""
from __future__ import annotations

from typing import Iterable, Sequence


def quantile(sorted_xs: Sequence[float], p: float) -> float:
    if not sorted_xs:
        raise ValueError("quantile of empty sample")
    if p < 0.0 or p > 1.0:
        raise ValueError(f"p out of range: {p}")
    n = len(sorted_xs)
    idx = (n - 1) * p
    lo = int(idx)
    hi = min(lo + 1, n - 1)
    frac = idx - lo
    return sorted_xs[lo] * (1.0 - frac) + sorted_xs[hi] * frac


def summarize(raw: Iterable[float]) -> dict:
    vals = [float(x) for x in raw]
    if not vals:
        raise ValueError("empty raw_repetitions")
    s = sorted(vals)
    q1 = quantile(s, 0.25)
    med = quantile(s, 0.50)
    q3 = quantile(s, 0.75)
    iqr = q3 - q1
    return {
        "n": len(vals),
        "median": med,
        "q1": q1,
        "q3": q3,
        "iqr": iqr,
        "noise_floor": iqr,
        "min": s[0],
        "max": s[-1],
    }


def classify_delta(claimed_delta: float, noise_floor: float) -> str:
    if abs(float(claimed_delta)) <= float(noise_floor):
        return "UNMEASURABLE"
    return "MEASURABLE"


def sample_indices(n_pool: int, n_keep: int, seed: int, bench_id: str) -> list[int]:
    """Deterministic draw of n_keep indices from range(n_pool), then sorted.

    Sorting keeps temporal order of the selected runs. The seed plus bench_id
    is the sampling frame a reviewer re-draws.
    """
    import random

    if n_keep > n_pool:
        raise ValueError("n_keep > n_pool")
    rng = random.Random(f"{seed}:{bench_id}")
    drawn = rng.sample(range(n_pool), n_keep)
    return sorted(drawn)
