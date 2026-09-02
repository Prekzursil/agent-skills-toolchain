"""Rank correlation and intervals. Stdlib only. Deterministic bootstrap."""
from __future__ import annotations

import math
import random
from typing import Sequence

BOOTSTRAP_N = 5000
BOOTSTRAP_SEED = 282
Z95 = 1.959963984540054


def average_ranks(values: Sequence[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda kv: kv[1])
    ranks = [0.0] * len(values)
    i = 0
    n = len(indexed)
    while i < n:
        j = i
        while j + 1 < n and indexed[j + 1][1] == indexed[i][1]:
            j += 1
        avg = 0.5 * (i + 1 + j + 1)
        for k in range(i, j + 1):
            ranks[indexed[k][0]] = avg
        i = j + 1
    return ranks


def pearson(xs: Sequence[float], ys: Sequence[float]) -> float:
    n = len(xs)
    if n != len(ys) or n < 2:
        return float("nan")
    mx = sum(xs) / n
    my = sum(ys) / n
    num = 0.0
    dx = 0.0
    dy = 0.0
    for a, b in zip(xs, ys):
        da = a - mx
        db = b - my
        num += da * db
        dx += da * da
        dy += db * db
    if dx <= 0.0 or dy <= 0.0:
        return float("nan")
    return num / math.sqrt(dx * dy)


def spearman(xs: Sequence[float], ys: Sequence[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        return float("nan")
    return pearson(average_ranks(xs), average_ranks(ys))


def _clamp_rho(rho: float) -> float:
    if math.isnan(rho):
        return rho
    return max(min(rho, 0.9999), -0.9999)


def fisher_z_ci(rho: float, n: int, z: float = Z95) -> tuple[float, float]:
    if n < 4 or math.isnan(rho):
        return float("nan"), float("nan")
    z0 = math.atanh(_clamp_rho(rho))
    se = 1.0 / math.sqrt(n - 3)
    lo = math.tanh(z0 - z * se)
    hi = math.tanh(z0 + z * se)
    return lo, hi


def bootstrap_spearman_ci(
    xs: Sequence[float],
    ys: Sequence[float],
    *,
    n_boot: int = BOOTSTRAP_N,
    seed: int = BOOTSTRAP_SEED,
) -> tuple[float, float]:
    n = len(xs)
    if n != len(ys) or n < 3:
        return float("nan"), float("nan")
    rng = random.Random(seed)
    samples: list[float] = []
    idx = list(range(n))
    for _ in range(n_boot):
        pick = [rng.choice(idx) for _ in range(n)]
        sx = [xs[i] for i in pick]
        sy = [ys[i] for i in pick]
        r = spearman(sx, sy)
        if not math.isnan(r):
            samples.append(r)
    if len(samples) < 50:
        return float("nan"), float("nan")
    samples.sort()
    lo_i = int(0.025 * (len(samples) - 1))
    hi_i = int(0.975 * (len(samples) - 1))
    return samples[lo_i], samples[hi_i]
