#!/usr/bin/env python3
"""Proper scoring rules + reliability diagram for resolved council forecasts."""
from __future__ import annotations

import math
import random
from typing import Any, Iterable

from corpus import (
    ALWAYS95,
    BOOTSTRAP_DRAWS,
    HAND_BRIER,
    HAND_CASES,
    SEED,
    WILSON_Z,
    build_forecasts_and_outcomes,
    resolve,
)

LOG_EPS = 1e-15


def clip_p(p: float) -> float:
    if p < LOG_EPS:
        return LOG_EPS
    if p > 1.0 - LOG_EPS:
        return 1.0 - LOG_EPS
    return p


def brier_mean(pairs: Iterable[tuple[float, int]]) -> float:
    rows = list(pairs)
    if not rows:
        raise ValueError("brier_mean: empty")
    return sum((p - y) ** 2 for p, y in rows) / len(rows)


def log_score_mean(pairs: Iterable[tuple[float, int]]) -> float:
    """Mean of y*ln(p)+(1-y)*ln(1-p). Higher (less negative) is better."""
    rows = list(pairs)
    if not rows:
        raise ValueError("log_score_mean: empty")
    acc = 0.0
    for p, y in rows:
        q = clip_p(float(p))
        acc += y * math.log(q) + (1 - y) * math.log(1.0 - q)
    return acc / len(rows)


def reliability_bins(
    pairs: Iterable[tuple[float, int]],
    *,
    width: float = 0.10,
) -> list[dict[str, Any]]:
    """Bins keyed by stated p (council uses discrete bands). Also fill width bins."""
    rows = list(pairs)
    by_p: dict[float, list[int]] = {}
    for p, y in rows:
        by_p.setdefault(float(p), []).append(int(y))
    discrete: list[dict[str, Any]] = []
    for p in sorted(by_p):
        ys = by_p[p]
        n = len(ys)
        hits = sum(ys)
        observed = hits / n
        discrete.append(
            {
                "bin": f"{p:.2f}",
                "stated_p": p,
                "predicted_confidence": p,
                "observed_accuracy": observed,
                "n": n,
                "n_correct": hits,
                "abs_gap": abs(observed - p),
            }
        )
    # Width bins (reliability diagram over [0,1]).
    width_bins: list[dict[str, Any]] = []
    n_width = int(round(1.0 / width))
    for i in range(n_width):
        lo = i * width
        hi = (i + 1) * width
        # Last bin includes 1.0.
        selected = [
            (p, y)
            for p, y in rows
            if (lo <= p < hi) or (i == n_width - 1 and p == hi)
        ]
        if not selected:
            continue
        n = len(selected)
        pred = sum(p for p, _ in selected) / n
        obs = sum(y for _, y in selected) / n
        width_bins.append(
            {
                "bin": f"[{lo:.2f},{hi:.2f}{']' if i == n_width - 1 else ')'}",
                "lo": lo,
                "hi": hi,
                "predicted_confidence": pred,
                "observed_accuracy": obs,
                "n": n,
                "n_correct": sum(y for _, y in selected),
                "abs_gap": abs(obs - pred),
            }
        )
    return discrete, width_bins


def wilson_interval(k: int, n: int, z: float = WILSON_Z) -> tuple[float, float, float]:
    if n <= 0:
        raise ValueError("wilson_interval: n<=0")
    phat = k / n
    z2 = z * z
    den = 1.0 + z2 / n
    centre = (phat + z2 / (2.0 * n)) / den
    margin = z * math.sqrt((phat * (1.0 - phat) + z2 / (4.0 * n)) / n) / den
    return phat, centre - margin, centre + margin


def percentile(xs: list[float], q: float) -> float:
    ys = sorted(xs)
    if not ys:
        raise ValueError("percentile: empty")
    idx = (len(ys) - 1) * q
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return ys[lo]
    w = idx - lo
    return ys[lo] * (1.0 - w) + ys[hi] * w


def paired_brier_delta(
    council: list[tuple[float, int]],
    control_p: float = ALWAYS95,
) -> list[float]:
    return [(control_p - y) ** 2 - (p - y) ** 2 for p, y in council]


def bootstrap_mean_ci(
    diffs: list[float],
    *,
    draws: int = BOOTSTRAP_DRAWS,
    seed: int = SEED,
) -> dict[str, float]:
    rng = random.Random(seed)
    n = len(diffs)
    if n == 0:
        raise ValueError("bootstrap_mean_ci: empty")
    means: list[float] = []
    for _ in range(draws):
        acc = 0.0
        for _i in range(n):
            acc += diffs[rng.randrange(n)]
        means.append(acc / n)
    point = sum(diffs) / n
    return {
        "point": point,
        "lo": percentile(means, 0.025),
        "hi": percentile(means, 0.975),
        "draws": float(draws),
        "seed": float(seed),
    }


def score_resolved(
    resolved: list[dict[str, Any]],
    *,
    p_key: str = "stated_p",
) -> dict[str, Any]:
    pairs = [(float(r[p_key]), int(r["y"])) for r in resolved]
    control_pairs = [(ALWAYS95, y) for _, y in pairs]
    discrete, width_bins = reliability_bins(pairs)
    diffs = paired_brier_delta(pairs)
    boot = bootstrap_mean_ci(diffs)
    bin80 = next((b for b in discrete if abs(b["stated_p"] - 0.80) < 1e-12), None)
    if bin80 is None:
        raise RuntimeError("no 0.80 band in resolved set")
    phat, lo, hi = wilson_interval(int(bin80["n_correct"]), int(bin80["n"]))
    brier = brier_mean(pairs)
    log_s = log_score_mean(pairs)
    brier95 = brier_mean(control_pairs)
    log95 = log_score_mean(control_pairs)
    return {
        "n_resolved": len(pairs),
        "brier": brier,
        "log_score": log_s,
        "log_loss": -log_s,
        "brier_always95": brier95,
        "log_score_always95": log95,
        "delta_brier_always95_minus_council": boot["point"],
        "delta_brier_bootstrap": boot,
        "control_separates": brier95 > brier and log95 < log_s,
        "reliability_discrete": discrete,
        "reliability_width": width_bins,
        "bin80": {
            **bin80,
            "wilson_phat": phat,
            "wilson_lo": lo,
            "wilson_hi": hi,
            "z": WILSON_Z,
        },
        "pairs": pairs,
    }


def honesty_mutation(forecasts, outcomes) -> dict[str, Any]:
    """Score unresolved as y=1. This is the illegal path the honesty probe rejects."""
    resolved, unresolved = resolve(forecasts, outcomes)
    mutated = list(resolved)
    for row in unresolved:
        clone = dict(row)
        clone["y"] = 1
        mutated.append(clone)
    honest = score_resolved(resolved)
    bad = score_resolved(mutated)
    return {
        "honest_n": honest["n_resolved"],
        "mutated_n": bad["n_resolved"],
        "unresolved_n": len(unresolved),
        "honest_brier": honest["brier"],
        "mutated_brier": bad["brier"],
        "n_inflated": bad["n_resolved"] > honest["n_resolved"],
        "brier_changed": abs(bad["brier"] - honest["brier"]) > 1e-15,
    }


def hand_brier() -> float:
    return brier_mean((c["p"], c["y"]) for c in HAND_CASES)


def full_report() -> dict[str, Any]:
    forecasts, outcomes = build_forecasts_and_outcomes()
    resolved, unresolved = resolve(forecasts, outcomes)
    scored = score_resolved(resolved)
    mut = honesty_mutation(forecasts, outcomes)
    hb = hand_brier()
    return {
        "seed": SEED,
        "forecasts": forecasts,
        "outcomes": outcomes,
        "resolved": resolved,
        "unresolved": unresolved,
        "n_forecasts": len(forecasts),
        "n_resolved": len(resolved),
        "n_unresolved": len(unresolved),
        "scored": scored,
        "honesty": mut,
        "hand_brier": hb,
        "hand_brier_expected": HAND_BRIER,
    }
