#!/usr/bin/env python3
"""Equal-weight linear / log opinion pools and history-using Bayesian / inverse-Brier weights.

Zero labelled outcomes: linear and log pools are defined; BMA and inverse-Brier
weights are not (InsufficientHistory).
"""
from __future__ import annotations

import math
import random
from typing import Iterable, Sequence

EPS = 1e-12


class InsufficientHistory(ValueError):
    """Raised when a method needs labelled (p, y) rows and receives none."""


def clip_p(p: float) -> float:
    return min(1.0 - EPS, max(EPS, float(p)))


def linear_pool(ps: Sequence[float], weights: Sequence[float] | None = None) -> float:
    n = len(ps)
    if n == 0:
        raise ValueError("empty pool")
    if weights is None:
        w = [1.0 / n] * n
    else:
        if len(weights) != n:
            raise ValueError("weight length")
        s = sum(weights)
        if s <= 0:
            raise ValueError("weights must sum > 0")
        w = [x / s for x in weights]
    return sum(w[i] * clip_p(ps[i]) for i in range(n))


def log_pool(ps: Sequence[float], weights: Sequence[float] | None = None) -> float:
    """Geometric / logarithmic opinion pool, renormalized on {y, 1-y} for binary p."""
    n = len(ps)
    if n == 0:
        raise ValueError("empty pool")
    if weights is None:
        w = [1.0 / n] * n
    else:
        if len(weights) != n:
            raise ValueError("weight length")
        s = sum(weights)
        if s <= 0:
            raise ValueError("weights must sum > 0")
        w = [x / s for x in weights]
    log_p = 0.0
    log_q = 0.0
    for i, p in enumerate(ps):
        pi = clip_p(p)
        log_p += w[i] * math.log(pi)
        log_q += w[i] * math.log(1.0 - pi)
    # p / (p+q) with p=exp(log_p), q=exp(log_q)
    m = max(log_p, log_q)
    num = math.exp(log_p - m)
    den = num + math.exp(log_q - m)
    return num / den


def brier(p: float, y: int) -> float:
    d = clip_p(p) - y
    return d * d


def inverse_brier_weights(history: Sequence[tuple[Sequence[float], int]]) -> list[float]:
    if not history:
        raise InsufficientHistory("inverse-Brier weights need labelled (forecast, outcome) rows")
    k = len(history[0][0])
    scores = [0.0] * k
    for ps, y in history:
        if len(ps) != k:
            raise ValueError("ragged member count")
        for i, p in enumerate(ps):
            scores[i] += brier(p, y)
    n = len(history)
    means = [s / n for s in scores]
    inv = [1.0 / max(m, EPS) for m in means]
    z = sum(inv)
    return [v / z for v in inv]


def bma_weights(history: Sequence[tuple[Sequence[float], int]]) -> list[float]:
    """Bernoulli-likelihood Bayesian model averaging over members (uniform prior)."""
    if not history:
        raise InsufficientHistory("BMA weights need labelled (forecast, outcome) rows")
    k = len(history[0][0])
    loglik = [0.0] * k
    for ps, y in history:
        if len(ps) != k:
            raise ValueError("ragged member count")
        for i, p in enumerate(ps):
            pi = clip_p(p)
            loglik[i] += math.log(pi if y else (1.0 - pi))
    m = max(loglik)
    w = [math.exp(ll - m) for ll in loglik]
    z = sum(w)
    return [v / z for v in w]


def ece(pairs: Iterable[tuple[float, int]], bins: int = 10) -> float:
    """Reliability term: bin-wise |freq - mean p| weighted by bin mass (ECE)."""
    buckets: list[list[tuple[float, int]]] = [[] for _ in range(bins)]
    rows = list(pairs)
    if not rows:
        return 0.0
    for p, y in rows:
        i = min(bins - 1, int(clip_p(p) * bins))
        buckets[i].append((p, y))
    n = len(rows)
    acc = 0.0
    for b in buckets:
        if not b:
            continue
        mp = sum(p for p, _ in b) / len(b)
        fy = sum(y for _, y in b) / len(b)
        acc += (len(b) / n) * abs(fy - mp)
    return acc


def _clip01(x: float) -> float:
    return min(1.0 - 1e-6, max(1e-6, x))


def simulate_panel(n: int, rng: random.Random) -> list[tuple[tuple[float, float, float], int]]:
    """Three members with unequal calibration, shared latent event probability."""
    out: list[tuple[tuple[float, float, float], int]] = []
    for _ in range(n):
        z = rng.gauss(0.0, 1.0)
        p_true = 1.0 / (1.0 + math.exp(-z))
        y = 1 if rng.random() < p_true else 0
        p_a = _clip01(p_true)  # calibrated
        p_b = _clip01(0.5 + 2.4 * (p_true - 0.5))  # overconfident
        p_c = _clip01(0.62)  # constant, badly calibrated
        out.append(((p_a, p_b, p_c), y))
    return out


def score_method(
    test: Sequence[tuple[tuple[float, float, float], int]],
    combine,
) -> dict:
    pairs = []
    bs = 0.0
    for ps, y in test:
        p = combine(ps)
        pairs.append((p, y))
        bs += brier(p, y)
    n = len(test)
    return {"brier": bs / n, "ece": ece(pairs), "n": n}


def run_control(seed: int = 79, n_train: int = 400, n_test: int = 2000) -> dict:
    rng = random.Random(seed)
    train = simulate_panel(n_train, rng)
    test = simulate_panel(n_test, rng)

    zero_ok = {}
    zero_blocked = {}
    try:
        zero_ok["linear_equal"] = linear_pool(test[0][0])
    except Exception as exc:  # pragma: no cover
        zero_blocked["linear_equal"] = type(exc).__name__
    try:
        zero_ok["log_equal"] = log_pool(test[0][0])
    except Exception as exc:  # pragma: no cover
        zero_blocked["log_equal"] = type(exc).__name__
    try:
        bma_weights([])
        zero_blocked["bma"] = "FAILED_TO_BLOCK"
    except InsufficientHistory:
        zero_blocked["bma"] = "InsufficientHistory"
    try:
        inverse_brier_weights([])
        zero_blocked["inverse_brier"] = "FAILED_TO_BLOCK"
    except InsufficientHistory:
        zero_blocked["inverse_brier"] = "InsufficientHistory"

    lin = score_method(test, lambda ps: linear_pool(ps))
    logp = score_method(test, lambda ps: log_pool(ps))
    w_bma = bma_weights(train)
    w_ib = inverse_brier_weights(train)
    bma = score_method(test, lambda ps: linear_pool(ps, w_bma))
    ib = score_method(test, lambda ps: linear_pool(ps, w_ib))
    log_ib = score_method(test, lambda ps: log_pool(ps, w_ib))

    return {
        "seed": seed,
        "n_train": n_train,
        "n_test": n_test,
        "zero_history_defined": sorted(zero_ok.keys()),
        "zero_history_blocked": zero_blocked,
        "bma_weights_after_history": w_bma,
        "inverse_brier_weights_after_history": w_ib,
        "scores": {
            "linear_equal_zero_history": lin,
            "log_equal_zero_history": logp,
            "bma_linear_with_history": bma,
            "inverse_brier_linear_with_history": ib,
            "inverse_brier_log_with_history": log_ib,
        },
    }
