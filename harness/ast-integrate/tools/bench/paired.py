"""Paired interval from case rows."""
from __future__ import annotations

import math
from typing import Any, Iterable


def _stats(xs: list[float]) -> tuple[float, float]:
    n = len(xs)
    mean = sum(xs) / n if n else 0.0
    if n < 2:
        return mean, 0.0
    var = sum((x - mean) ** 2 for x in xs) / (n - 1)
    return mean, math.sqrt(var)


def paired_from_cases(cases: Iterable[dict[str, Any]], change_id: str) -> dict[str, Any]:
    rows = list(cases)
    primary = [float(r["treatment"]) - float(r["control"]) for r in rows]
    secondary = [
        float(r.get("secondary_treatment", 0.0)) - float(r.get("secondary_control", 0.0))
        for r in rows
    ]
    n = len(rows)
    mean, sd = _stats(primary)
    se = sd / math.sqrt(n) if n else 0.0
    z = 1.96
    lo, hi = mean - z * se, mean + z * se
    smean, ssd = _stats(secondary)
    sse = ssd / math.sqrt(n) if n else 0.0
    return {
        "change_id": change_id,
        "n": n,
        "point_estimate": mean,
        "interval": {"mean": mean, "lo": lo, "hi": hi, "n": n, "sd": sd},
        "secondary": {
            "mean": smean,
            "lo": smean - z * sse,
            "hi": smean + z * sse,
            "n": n,
        },
    }
