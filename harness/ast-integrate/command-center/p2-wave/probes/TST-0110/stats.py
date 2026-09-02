"""Variance band and MDE from raw per-run numbers (never from a summary)."""
from __future__ import annotations

from typing import Sequence


def mean(xs: Sequence[float]) -> float:
    if not xs:
        raise ValueError("mean of empty sample")
    return float(sum(xs)) / float(len(xs))


def stdev(xs: Sequence[float]) -> float:
    """Sample standard deviation (ddof=1). Exact identical runs measure 0."""
    n = len(xs)
    if n < 2:
        return 0.0
    m = mean(xs)
    acc = 0.0
    for x in xs:
        d = float(x) - m
        acc += d * d
    return (acc / float(n - 1)) ** 0.5


def mde(std: float, n: int, floor: float = 1.0) -> float:
    """Minimum detectable effect for a two-sample mean difference.

    3 * std * sqrt(2/n), floored at 1.0 so an exact integer instrument
    still treats a one-count move as distinguishable. std=0 is measured
    (identical raw runs), not assumed.
    """
    if n < 2:
        return floor
    if std <= 0.0:
        return floor
    return max(floor, 3.0 * float(std) * ((2.0 / float(n)) ** 0.5))


def significant(delta: float, band: float) -> bool:
    return abs(float(delta)) >= float(band)


def rederive(raw: Sequence[float]) -> dict:
    xs = [float(x) for x in raw]
    n = len(xs)
    s = stdev(xs)
    return {
        "n": n,
        "mean": mean(xs),
        "std": s,
        "mde": mde(s, n),
        "raw": xs,
    }
