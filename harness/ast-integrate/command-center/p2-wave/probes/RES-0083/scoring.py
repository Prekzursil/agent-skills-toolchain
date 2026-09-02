#!/usr/bin/env python3
"""Proper scores and the Karmarkar/extremizing map used in GJP papers.

Binary Brier is the two-component form used by Mellers et al. 2014 and
Atanasov et al. 2017 (range 0 best to 2 worst):
    (p - y)^2 + ((1-p) - (1-y))^2  ==  2 (p - y)^2
"""
from __future__ import annotations

import math


def brier_binary(p: float, y: int) -> float:
    if y not in (0, 1):
        raise ValueError("y must be 0 or 1")
    if not 0.0 <= p <= 1.0:
        raise ValueError("p must be in [0, 1]")
    return (p - y) ** 2 + ((1.0 - p) - (1 - y)) ** 2


def log_score_binary(p: float, y: int, clip: float = 1e-15) -> float:
    """Negative log score (lower is better), matching a proper penalty."""
    if y not in (0, 1):
        raise ValueError("y must be 0 or 1")
    q = min(max(p, clip), 1.0 - clip)
    return -math.log(q if y == 1 else (1.0 - q))


def spherical_binary(p: float, y: int) -> float:
    """Spherical score in [0, 1]; higher is better (Gneiting & Raftery 2007)."""
    if y not in (0, 1):
        raise ValueError("y must be 0 or 1")
    norm = math.sqrt(p * p + (1.0 - p) * (1.0 - p))
    return (p if y == 1 else (1.0 - p)) / norm


def extremize(p: float, a: float) -> float:
    """Baron et al. 2014 eq. (1): t(p) = p^a / (p^a + (1-p)^a)."""
    if a <= 0:
        raise ValueError("a must be positive")
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return 1.0
    num = p**a
    den = num + (1.0 - p) ** a
    return num / den


def mellers_worked_example() -> dict:
    """Mellers et al. 2014 Methods: 90% on a binary event."""
    hit = brier_binary(0.9, 1)
    miss = brier_binary(0.9, 0)
    return {
        "p": 0.9,
        "brier_if_occurs": hit,
        "brier_if_not": miss,
        "expected_hit": 0.02,
        "expected_miss": 1.62,
    }
