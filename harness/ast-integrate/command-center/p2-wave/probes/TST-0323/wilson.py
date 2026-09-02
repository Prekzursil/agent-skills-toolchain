#!/usr/bin/env python3
"""Wilson score interval for a binomial error rate.

Wald 0/n collapses to [0, 0]; Wilson 0/n has high = z^2 / (n + z^2).
That identity is the wiring control: a Wald implementation fails it.
"""
from __future__ import annotations

import math
from statistics import NormalDist

Z_95 = NormalDist().inv_cdf(0.975)


def wilson_interval(k: int, n: int, z: float = Z_95) -> dict:
    if n <= 0:
        return {
            "defined": False,
            "k": k,
            "n": n,
            "rate": None,
            "low": None,
            "high": None,
            "method": "wilson_score",
            "z": z,
            "alpha": 0.05,
        }
    if k < 0 or k > n:
        raise ValueError(f"k={k} outside [0, n={n}]")
    phat = k / n
    z2 = z * z
    den = 1.0 + z2 / n
    center = (phat + z2 / (2.0 * n)) / den
    inner = phat * (1.0 - phat) / n + z2 / (4.0 * n * n)
    margin = z * math.sqrt(inner) / den
    low = max(0.0, center - margin)
    high = min(1.0, center + margin)
    return {
        "defined": True,
        "k": k,
        "n": n,
        "rate": phat,
        "low": low,
        "high": high,
        "center": center,
        "margin": margin,
        "method": "wilson_score",
        "z": z,
        "alpha": 0.05,
    }


def wilson_zero_n_high(n: int, z: float = Z_95) -> float:
    """Closed form for k=0: high = z^2 / (n + z^2), low = 0."""
    z2 = z * z
    return z2 / (n + z2)
