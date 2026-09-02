"""Library variance band / MDE from a raw vector (TST-0109).

Every summary number is derived from the raw vector handed in; nothing is
accepted from a summary. An empty vector is refused with EmptyInputError
instead of emitting a number.
"""
from __future__ import annotations

import math
from statistics import NormalDist
from typing import Any

ALPHA = 0.05
POWER = 0.80
CLAIMED_RELATIVE_EFFECT = 0.05

_Z = NormalDist()
Z_ALPHA = _Z.inv_cdf(1.0 - ALPHA / 2.0)
Z_BETA = _Z.inv_cdf(POWER)
Z_SUM = Z_ALPHA + Z_BETA

FORMULA = (
    "mean = sum(raw)/n; stdev = sqrt(sum((x-mean)^2)/(n-1)); "
    "se_mean = stdev/sqrt(n); variance_band = mean -/+ z(1-alpha/2)*se_mean; "
    "MDE = (z(1-alpha/2) + z(power)) * stdev * sqrt(2/n); "
    "n_min(delta) = ceil(2*((z(1-alpha/2)+z(power))*stdev/delta)^2) "
    "with alpha=0.05, power=0.80, delta = 5% of mean"
)


class EmptyInputError(ValueError):
    """Raised when a band is requested for an empty raw vector."""


def mean(raw: list[float]) -> float:
    if not raw:
        raise EmptyInputError("empty raw vector: refusing to emit a number")
    return sum(raw) / float(len(raw))


def sample_stdev(raw: list[float]) -> float:
    n = len(raw)
    if n < 2:
        return 0.0
    mu = mean(raw)
    return math.sqrt(sum((x - mu) ** 2 for x in raw) / float(n - 1))


def mde(stdev: float, n: int) -> float:
    """Minimum detectable effect for a two-sample comparison at alpha/power."""
    if n < 2 or stdev == 0.0:
        return 0.0
    return float(Z_SUM * stdev * math.sqrt(2.0 / float(n)))


def n_min_for_delta(stdev: float, delta: float) -> int:
    if delta <= 0:
        raise ValueError("non-positive claimed delta")
    if stdev == 0.0:
        return 2
    need = 2.0 * ((Z_SUM * stdev) / float(delta)) ** 2
    return max(2, int(math.ceil(need - 1e-12)))


def band_from_raw(
    bid: str,
    raw: list[float],
    *,
    metric: str | None = None,
    input_cardinality: int | None = None,
    sha: str | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    if not raw:
        raise EmptyInputError(f"{bid}: empty raw vector")
    values = [float(x) for x in raw]
    n = len(values)
    mu = mean(values)
    sd = sample_stdev(values)
    se = sd / math.sqrt(n) if sd else 0.0
    half = Z_ALPHA * se
    detectable = mde(sd, n)
    claimed_abs = abs(mu) * CLAIMED_RELATIVE_EFFECT if mu != 0 else None
    return {
        "id": bid,
        "n": n,
        "mean": mu,
        "stdev": sd,
        "se_mean": se,
        "variance_band": {"low": mu - half, "high": mu + half},
        "mde": detectable,
        "mde_relative_to_mean": (detectable / abs(mu)) if mu != 0 else None,
        "claimed_relative_effect": CLAIMED_RELATIVE_EFFECT,
        "claimed_absolute_effect": claimed_abs,
        "n_min_for_claimed_5pct": n_min_for_delta(sd, claimed_abs) if claimed_abs else None,
        "alpha": ALPHA,
        "power": POWER,
        "metric": metric,
        "input_cardinality": input_cardinality,
        "sha": sha,
        "seed": seed,
        "raw": values,
    }
