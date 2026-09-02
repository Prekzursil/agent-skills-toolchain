"""Tukey hinges / median / IQR. Method is documented and must be re-derived."""
from __future__ import annotations

from typing import Sequence


def sorted_nums(values: Sequence[float]) -> list[float]:
    return sorted(float(v) for v in values)


def median(values: Sequence[float]) -> float:
    ys = sorted_nums(values)
    n = len(ys)
    if n == 0:
        raise ValueError("median of empty")
    if n % 2:
        return ys[n // 2]
    return (ys[n // 2 - 1] + ys[n // 2]) / 2.0


def tukey_hinges(values: Sequence[float]) -> tuple[float, float, float]:
    """Return (q1, median, q3) using Tukey hinges (split at median, exclude mid if odd)."""
    ys = sorted_nums(values)
    n = len(ys)
    if n < 2:
        m = median(ys)
        return m, m, m
    m = median(ys)
    if n % 2:
        lower, upper = ys[: n // 2], ys[n // 2 + 1 :]
    else:
        lower, upper = ys[: n // 2], ys[n // 2 :]
    return median(lower), m, median(upper)


def iqr(values: Sequence[float]) -> float:
    q1, _, q3 = tukey_hinges(values)
    return q3 - q1


def interval_block(values: Sequence[float]) -> dict:
    ys = sorted_nums(values)
    q1, med, q3 = tukey_hinges(ys)
    return {
        "n": len(ys),
        "raw_sorted": ys,
        "q1": q1,
        "median": med,
        "q3": q3,
        "iqr": q3 - q1,
        "method": "tukey-hinges-exclude-odd-median",
    }
