"""Bootstrap CIs, paired Cohen's d_z, Welford mean (reviewer path)."""
from __future__ import annotations

import math
import random
from typing import Sequence

BOOTSTRAP_N = 2000
BOOTSTRAP_SEED = 289
CI_LEVEL = 0.95


def welford_mean(xs: Sequence[float]) -> float:
    n = 0
    mean = 0.0
    for x in xs:
        n += 1
        mean += (float(x) - mean) / n
    if n == 0:
        return 0.0
    return mean


def sample_sd(xs: Sequence[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    m = welford_mean(xs)
    acc = sum((float(x) - m) ** 2 for x in xs)
    return math.sqrt(acc / (n - 1))


def cohens_dz(deltas: Sequence[float]) -> float | None:
    sd = sample_sd(deltas)
    m = welford_mean(deltas)
    if sd < 1e-15:
        return 0.0 if abs(m) < 1e-15 else None
    return m / sd


def bootstrap_mean_ci(
    xs: Sequence[float],
    *,
    n_boot: int = BOOTSTRAP_N,
    seed: int = BOOTSTRAP_SEED,
    level: float = CI_LEVEL,
) -> dict[str, float]:
    values = [float(x) for x in xs]
    n = len(values)
    mean = welford_mean(values)
    if n == 0:
        return {"mean": 0.0, "lo": 0.0, "hi": 0.0, "n": 0.0, "level": level}
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(n_boot):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(welford_mean(sample))
    means.sort()
    lo_i = int((1.0 - level) / 2.0 * n_boot)
    hi_i = int((1.0 + level) / 2.0 * n_boot) - 1
    lo_i = max(0, min(n_boot - 1, lo_i))
    hi_i = max(0, min(n_boot - 1, hi_i))
    return {
        "mean": mean,
        "lo": means[lo_i],
        "hi": means[hi_i],
        "n": float(n),
        "level": level,
        "n_boot": float(n_boot),
    }


def normal_mean_ci(
    xs: Sequence[float], *, z: float = 1.96, level: float = CI_LEVEL
) -> dict[str, float]:
    values = [float(x) for x in xs]
    n = len(values)
    m = welford_mean(values)
    if n < 2:
        return {"mean": m, "lo": m, "hi": m, "n": float(n), "level": level}
    se = sample_sd(values) / math.sqrt(n)
    return {
        "mean": m,
        "lo": m - z * se,
        "hi": m + z * se,
        "n": float(n),
        "level": level,
        "se": se,
    }


def ci_excludes_zero(ci: dict[str, float]) -> bool:
    return not (float(ci["lo"]) <= 0.0 <= float(ci["hi"]))
