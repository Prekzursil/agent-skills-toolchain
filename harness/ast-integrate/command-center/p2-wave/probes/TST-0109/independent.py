"""Independent statistics reviewer arithmetic for TST-0109.

Does not import tools/variance_band/stats.py. Re-derives mean, sample
standard deviation, MDE, and n_min from a raw vector using stdlib only.
A five-point hand fixture is derived in comments, not copied from a summary.
"""
from __future__ import annotations

import math
from statistics import NormalDist

ALPHA = 0.05
POWER = 0.80
_Z = NormalDist()
Z_ALPHA = _Z.inv_cdf(1.0 - ALPHA / 2.0)
Z_BETA = _Z.inv_cdf(POWER)
Z_SUM = Z_ALPHA + Z_BETA

# Hand fixture (TST-0109 statistics reviewer):
# values 10, 12, 11, 13, 14
# sum = 60; n = 5; mean = 60/5 = 12
# squared deviations: (10-12)^2=4, (12-12)^2=0, (11-12)^2=1,
#                     (13-12)^2=1, (14-12)^2=4; ss = 10
# sample variance = 10/(5-1) = 2.5
HAND_ID = "hand-derived-five"
HAND_RAW = [10.0, 12.0, 11.0, 13.0, 14.0]
HAND_N = 5
HAND_SUM = 60.0
HAND_MEAN = 12.0
HAND_SS = 10.0
HAND_VAR = 2.5


def mean(raw: list[float]) -> float:
    if not raw:
        raise ValueError("empty-raw-refused")
    return sum(raw) / float(len(raw))


def sample_stdev(raw: list[float]) -> float:
    n = len(raw)
    if n < 2:
        raise ValueError("n-lt-2-refused")
    mu = mean(raw)
    ss = sum((x - mu) ** 2 for x in raw)
    return math.sqrt(ss / float(n - 1))


def mde(stdev: float, n: int) -> float:
    if n < 2:
        raise ValueError("n-lt-2-refused")
    if stdev == 0.0:
        return 0.0
    return float(Z_SUM * stdev * math.sqrt(2.0 / float(n)))


def n_min_for_delta(stdev: float, delta: float) -> int:
    if delta <= 0:
        raise ValueError("non-positive-claimed-delta-refused")
    if stdev == 0.0:
        return 2
    need = 2.0 * ((Z_SUM * stdev) / float(delta)) ** 2
    return max(2, int(math.ceil(need - 1e-12)))


def recompute(raw: list[float]) -> dict:
    n = len(raw)
    mu = mean(raw)
    s = sample_stdev(raw)
    se = s / math.sqrt(n) if s else 0.0
    half = Z_ALPHA * se
    detectable = mde(s, n)
    claimed_abs = abs(mu) * 0.05 if mu != 0 else None
    return {
        "n": n,
        "mean": mu,
        "stdev": s,
        "se_mean": se,
        "band_low": mu - half,
        "band_high": mu + half,
        "mde": detectable,
        "n_min_for_claimed_5pct": (
            n_min_for_delta(s, claimed_abs) if claimed_abs else None
        ),
    }


def hand_oracle() -> dict:
    stdev = math.sqrt(HAND_VAR)
    return {
        "id": HAND_ID,
        "n": HAND_N,
        "mean": HAND_MEAN,
        "stdev": stdev,
        "mde": mde(stdev, HAND_N),
        "raw": list(HAND_RAW),
    }


def close(a: float, b: float, rel: float = 1e-9, abs_tol: float = 1e-6) -> bool:
    return abs(float(a) - float(b)) <= max(abs_tol, rel * max(abs(float(a)), abs(float(b))))
