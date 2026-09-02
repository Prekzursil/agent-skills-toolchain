"""Binomial interval arithmetic for CNF-0020.

Wilson score interval is the primary reported interval (no extra deps).
Clopper-Pearson is computed by binary search on the binomial CDF.
"""
from __future__ import annotations

import math
from typing import Any

Z95 = 1.959963984540054
CONFIDENCE = 0.95
ALPHA = 1.0 - CONFIDENCE


def classify(k: int, n: int) -> str:
    if n <= 0:
        raise ValueError("n must be positive")
    if k == n:
        return "deterministic"
    if k == 0:
        return "not-reproduced"
    return "intermittent"


def wilson(k: int, n: int, z: float = Z95) -> tuple[float, float]:
    if n <= 0:
        raise ValueError("n must be positive")
    if k < 0 or k > n:
        raise ValueError("k out of range")
    p = k / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2.0 * n)) / denom
    rad = (z * math.sqrt((p * (1.0 - p) + z2 / (4.0 * n)) / n)) / denom
    low = max(0.0, center - rad)
    high = min(1.0, center + rad)
    return low, high


def _binom_cdf(k: int, n: int, p: float) -> float:
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    if p <= 0.0:
        return 1.0
    if p >= 1.0:
        return 1.0 if k >= n else 0.0
    total = 0.0
    q = 1.0 - p
    for i in range(k + 1):
        total += math.comb(n, i) * (p**i) * (q ** (n - i))
    return total


def _binom_sf(k: int, n: int, p: float) -> float:
    """P(X >= k)."""
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    return 1.0 - _binom_cdf(k - 1, n, p)


def _invert(fn, target: float) -> float:
    lo, hi = 0.0, 1.0
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if fn(mid) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def clopper_pearson(k: int, n: int, alpha: float = ALPHA) -> tuple[float, float]:
    if n <= 0:
        raise ValueError("n must be positive")
    if k < 0 or k > n:
        raise ValueError("k out of range")
    half = alpha / 2.0
    # Lower: p such that P(X >= k | n,p) = alpha/2 (survival increases with p).
    # Upper: p such that P(X <= k | n,p) = alpha/2 (cdf decreases with p).
    if k == 0:
        low = 0.0
    else:
        low = _invert(lambda p: _binom_sf(k, n, p), half)
    if k == n:
        high = 1.0
    else:
        high = _invert(lambda p: -_binom_cdf(k, n, p), -half)
    if low > high:
        low, high = high, low
    return max(0.0, min(1.0, low)), max(0.0, min(1.0, high))


def round6(x: float) -> float:
    return float(f"{x:.6f}")


def interval_block(k: int, n: int) -> dict[str, Any]:
    wlo, whi = wilson(k, n)
    clo, chi = clopper_pearson(k, n)
    return {
        "method": "wilson",
        "confidence": CONFIDENCE,
        "low": round6(wlo),
        "high": round6(whi),
        "clopper_pearson": {
            "method": "clopper-pearson",
            "confidence": CONFIDENCE,
            "low": round6(clo),
            "high": round6(chi),
        },
        "k": k,
        "n": n,
        "p_hat": round6(k / n) if n else 0.0,
    }
