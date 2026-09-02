#!/usr/bin/env python3
"""Wilson score interval for a binomial survival rate."""
from __future__ import annotations

import math

Z_95 = 1.959963984540054


def wilson_interval(k, n, z=Z_95):
    if n <= 0:
        raise ValueError("wilson_interval requires n >= 1")
    if k < 0 or k > n:
        raise ValueError("k must be in [0, n]")
    p = k / n
    z2 = z * z
    den = 1.0 + z2 / n
    center = (p + z2 / (2.0 * n)) / den
    rad = z * math.sqrt((p * (1.0 - p) + z2 / (4.0 * n)) / n) / den
    return {
        "alpha": 0.05,
        "center": center,
        "high": min(1.0, center + rad),
        "low": max(0.0, center - rad),
        "method": "wilson_score",
        "z": z,
    }
