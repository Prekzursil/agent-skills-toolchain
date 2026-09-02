#!/usr/bin/env python3
"""Distribution regression gate: median + p95 with stated variance, n>=k.

A single sample cannot produce a verdict. When n < k the gate returns
REFUSED (not PASS, not REGRESSION). Spread is reported next to every
point estimate.

Higher values are worse (latency-like). A >=20% relative rise in median
or p95 is REGRESSION. A 2% band is not flagged.
"""
from __future__ import annotations

import math
import random
import statistics
from statistics import NormalDist
from typing import Any, Sequence

DEFAULT_K = 11
NOISE_BAND = 0.02
REGRESSION_THRESHOLD = 0.20
SYNTHETIC_N = 200
SYNTHETIC_MU = 100.0
SYNTHETIC_SIGMA = 10.0
FPR_RUNS = 100
FPR_SEED = 20260824
FPR_MU = 100.0
FPR_SIGMA = 5.0
REL_EPS = 1e-12


def linear_percentile(values: Sequence[float], p: float) -> float:
    if not 0.0 <= p <= 1.0:
        raise ValueError(f"percentile p out of range: {p}")
    ordered = sorted(float(x) for x in values)
    n = len(ordered)
    if n == 0:
        raise ValueError("percentile of empty sample")
    if n == 1:
        return ordered[0]
    idx = p * (n - 1)
    lo = int(math.floor(idx))
    hi = min(lo + 1, n - 1)
    frac = idx - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


def median_two_way(values: Sequence[float]) -> dict[str, Any]:
    xs = [float(x) for x in values]
    a = float(statistics.median(xs))
    ordered = sorted(xs)
    n = len(ordered)
    if n == 0:
        raise ValueError("median of empty sample")
    if n % 2 == 1:
        b = float(ordered[n // 2])
    else:
        b = (ordered[n // 2 - 1] + ordered[n // 2]) / 2.0
    return {
        "method_a": {"name": "statistics.median", "value": a},
        "method_b": {"name": "middle-index", "value": b},
        "agree": abs(a - b) <= REL_EPS,
        "value": a,
    }


def summarize(values: Sequence[float]) -> dict[str, Any]:
    xs = [float(x) for x in values]
    n = len(xs)
    if n == 0:
        raise ValueError("empty sample")
    med = median_two_way(xs)
    if not med["agree"]:
        raise ValueError("median two-way disagreement")
    p95 = linear_percentile(xs, 0.95)
    if n >= 2:
        var = float(statistics.variance(xs))
        sd = float(statistics.stdev(xs))
        iqr = linear_percentile(xs, 0.75) - linear_percentile(xs, 0.25)
    else:
        var = None
        sd = None
        iqr = None
    return {
        "n": n,
        "median": med["value"],
        "p95": p95,
        "variance": var,
        "stdev": sd,
        "iqr": iqr,
        "median_two_way": med,
    }


def _rel_change(new: float, old: float) -> float:
    if old == 0.0:
        raise ValueError("baseline point estimate is zero; relative change undefined")
    return (new - old) / abs(old)


def compare(
    baseline: Sequence[float],
    candidate: Sequence[float],
    *,
    k: int = DEFAULT_K,
    noise_band: float = NOISE_BAND,
    regression_threshold: float = REGRESSION_THRESHOLD,
) -> dict[str, Any]:
    """Compare candidate vs baseline as distributions.

    Returns verdict REFUSED when n < k on either side. Never issues
    REGRESSION or NO_REGRESSION from a single sample.
    """
    if k < 2:
        raise ValueError("k must be >= 2 so a variance exists")
    base = [float(x) for x in baseline]
    cand = [float(x) for x in candidate]
    n_b, n_c = len(base), len(cand)
    out: dict[str, Any] = {
        "k": k,
        "n_baseline": n_b,
        "n_candidate": n_c,
        "noise_band": noise_band,
        "regression_threshold": regression_threshold,
        "higher_is_worse": True,
        "compares": ["median", "p95"],
        "spread_fields": ["variance", "stdev", "iqr"],
    }
    if n_b < k or n_c < k:
        out.update(
            {
                "verdict": "REFUSED",
                "reason": "n<k",
                "issued": False,
                "point_estimate_only": False,
            }
        )
        return out
    b = summarize(base)
    c = summarize(cand)
    median_rel = _rel_change(c["median"], b["median"])
    p95_rel = _rel_change(c["p95"], b["p95"])
    worst_rel = max(median_rel, p95_rel)
    inside_noise = worst_rel <= noise_band
    if worst_rel >= regression_threshold:
        verdict = "REGRESSION"
    else:
        verdict = "NO_REGRESSION"
    out.update(
        {
            "verdict": verdict,
            "reason": "distribution-compare",
            "issued": True,
            "point_estimate_only": False,
            "baseline": b,
            "candidate": c,
            "median_relative_change": median_rel,
            "p95_relative_change": p95_rel,
            "worst_relative_change": worst_rel,
            "inside_noise_band": inside_noise,
            "spread_reported": True,
            "stated_variance": {
                "baseline": b["variance"],
                "candidate": c["variance"],
                "baseline_stdev": b["stdev"],
                "candidate_stdev": c["stdev"],
                "baseline_iqr": b["iqr"],
                "candidate_iqr": c["iqr"],
            },
        }
    )
    return out


def inverse_cdf_normal(n: int, mu: float, sigma: float) -> list[float]:
    """Deterministic synthetic sample: Normal inverse-CDF at plotting positions."""
    if n < 1:
        raise ValueError("n>=1 required")
    if sigma <= 0:
        raise ValueError("sigma must be positive")
    nd = NormalDist(mu, sigma)
    return [nd.inv_cdf((i + 0.5) / n) for i in range(n)]


def analytic_normal(mu: float, sigma: float) -> dict[str, float]:
    nd = NormalDist(mu, sigma)
    return {
        "median": float(mu),
        "p95": float(nd.inv_cdf(0.95)),
        "variance": float(sigma * sigma),
        "stdev": float(sigma),
    }


def scaled_normal(mu: float, sigma: float, scale: float) -> tuple[float, float]:
    return mu * scale, sigma * scale


def no_change_false_positive_rate(
    *,
    n_runs: int = FPR_RUNS,
    n: int = DEFAULT_K,
    mu: float = FPR_MU,
    sigma: float = FPR_SIGMA,
    seed: int = FPR_SEED,
    k: int = DEFAULT_K,
) -> dict[str, Any]:
    rng = random.Random(seed)
    flags = 0
    refused = 0
    for _ in range(n_runs):
        base = [rng.gauss(mu, sigma) for _ in range(n)]
        cand = [rng.gauss(mu, sigma) for _ in range(n)]
        r = compare(base, cand, k=k)
        if r["verdict"] == "REGRESSION":
            flags += 1
        elif r["verdict"] == "REFUSED":
            refused += 1
    return {
        "n_runs": n_runs,
        "n": n,
        "k": k,
        "mu": mu,
        "sigma": sigma,
        "seed": seed,
        "regression_flags": flags,
        "refused": refused,
        "false_positive_rate": flags / n_runs if n_runs else None,
    }


def jsonable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [jsonable(v) for v in obj]
    if isinstance(obj, bool) or obj is None:
        return obj
    if isinstance(obj, int) and not isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise ValueError("non-finite float")
        return obj
    if isinstance(obj, str):
        return obj
    raise TypeError(f"not jsonable: {type(obj)!r}")


def constant_sample(value: float, n: int) -> list[float]:
    return [float(value)] * n


def both_states_controls(*, k: int = DEFAULT_K) -> dict[str, Any]:
    base = constant_sample(100.0, k)
    return {
        "regression_20pct": compare(base, constant_sample(120.0, k), k=k),
        "noise_2pct": compare(base, constant_sample(102.0, k), k=k),
    }


def n_lt_k_controls(*, k: int = DEFAULT_K) -> dict[str, Any]:
    return {
        "single_sample": compare([100.0], [120.0], k=k),
        "n_k_minus_1_with_50pct": compare(
            constant_sample(100.0, k - 1),
            constant_sample(150.0, k - 1),
            k=k,
        ),
        "n_equals_k_no_change": compare(
            constant_sample(100.0, k),
            constant_sample(100.0, k),
            k=k,
        ),
    }


def synthetic_known_distribution(
    *,
    n: int = SYNTHETIC_N,
    mu: float = SYNTHETIC_MU,
    sigma: float = SYNTHETIC_SIGMA,
    k: int = DEFAULT_K,
) -> dict[str, Any]:
    mu20, s20 = scaled_normal(mu, sigma, 1.0 + REGRESSION_THRESHOLD)
    mu2, s2 = scaled_normal(mu, sigma, 1.0 + NOISE_BAND)
    base = inverse_cdf_normal(n, mu, sigma)
    cand20 = inverse_cdf_normal(n, mu20, s20)
    cand2 = inverse_cdf_normal(n, mu2, s2)
    pop_base = analytic_normal(mu, sigma)
    pop_20 = analytic_normal(mu20, s20)
    pop_2 = analytic_normal(mu2, s2)
    gate_20 = compare(base, cand20, k=k)
    gate_2 = compare(base, cand2, k=k)
    return {
        "n": n,
        "k": k,
        "baseline_params": {"mu": mu, "sigma": sigma, "family": "Normal"},
        "shift_20pct_params": {"mu": mu20, "sigma": s20, "family": "Normal"},
        "shift_2pct_params": {"mu": mu2, "sigma": s2, "family": "Normal"},
        "population_baseline": pop_base,
        "population_20pct": pop_20,
        "population_2pct": pop_2,
        "analytic_verdict_20pct": "REGRESSION",
        "analytic_verdict_2pct": "NO_REGRESSION",
        "gate_20pct": gate_20,
        "gate_2pct": gate_2,
        "baseline_samples": base,
        "candidate_20pct_samples": cand20,
        "candidate_2pct_samples": cand2,
    }


def rel_err(observed: float, analytic: float) -> float:
    return abs(observed - analytic) / abs(analytic) if analytic != 0 else abs(observed)
