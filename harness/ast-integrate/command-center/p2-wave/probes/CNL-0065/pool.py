#!/usr/bin/env python3
"""Linear vs logarithmic pooling under a same-vendor correlation DGP.

Closed form (equal-prior binary Y, Gaussian signals):

  X_i = (2Y-1)*mu + Z + eps_i
  Z ~ N(0, tau^2)                 shared vendor / prompt shock
  eps_i ~ N(0, sigma^2)           idiosyncratic remainder

Joint covariance: Sigma = sigma^2 I + tau^2 11^T.
True log-likelihood ratio given the panel:

  llr_true = 2 * mu * sum(X) / (sigma^2 + n * tau^2)     # CNL-0065-CLOSED-FORM

Independence-assuming product of *marginal* likelihoods (unnormalized
logarithmic pool with per-seat weight 1, weights sum to n):

  llr_indep = 2 * mu * sum(X) / (sigma^2 + tau^2)        # CNL-0065-INDEP-BAYES

Log-odds inflation factor (tau>0, n>1):

  (sigma^2 + n*tau^2) / (sigma^2 + tau^2)                # CNL-0065-INFLATION

Normalized logarithmic pool (weights sum to 1) averages log-odds and does
not multiply evidence. Linear pool averages probabilities and likewise
does not assume independence.
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
N_SEATS = 5
MU = 1.0
SIGMA = 1.0
TAU_CORRELATED = 1.5
TAU_INDEPENDENT = 0.0
N_TRIALS = 4000
SEED = 65
# Worked example: five same-vendor seats, shared shock visible in the X vector.
CANONICAL_X = [1.20, 1.05, 1.35, 0.95, 1.15]


def sigmoid(llr: float) -> float:
    if llr >= 0:
        z = math.exp(-llr)
        return 1.0 / (1.0 + z)
    z = math.exp(llr)
    return z / (1.0 + z)


def variance_terms(sigma: float, tau: float) -> tuple[float, float]:
    return sigma * sigma, tau * tau


def inflation_factor(n: int, sigma: float, tau: float) -> float:
    """CNL-0065-INFLATION: llr_indep / llr_true when the sums match."""
    sigma2, tau2 = variance_terms(sigma, tau)
    denom = sigma2 + tau2
    if denom == 0:
        raise ZeroDivisionError("sigma and tau both zero")
    return (sigma2 + n * tau2) / denom


def llr_true(xs: list[float], mu: float, sigma: float, tau: float) -> float:
    """CNL-0065-CLOSED-FORM joint posterior log-odds at prior 1:1."""
    n = len(xs)
    sigma2, tau2 = variance_terms(sigma, tau)
    return 2.0 * mu * sum(xs) / (sigma2 + n * tau2)


def llr_indep_bayes(xs: list[float], mu: float, sigma: float, tau: float) -> float:
    """CNL-0065-INDEP-BAYES product of marginal likelihood ratios, one prior."""
    sigma2, tau2 = variance_terms(sigma, tau)
    v = sigma2 + tau2
    return 2.0 * mu * sum(xs) / v


def seat_logodds(x: float, mu: float, sigma: float, tau: float) -> float:
    sigma2, tau2 = variance_terms(sigma, tau)
    return 2.0 * mu * x / (sigma2 + tau2)


def seat_probs(xs: list[float], mu: float, sigma: float, tau: float) -> list[float]:
    return [sigmoid(seat_logodds(x, mu, sigma, tau)) for x in xs]


def linear_pool(probs: list[float]) -> float:
    if not probs:
        raise ValueError("empty panel")
    return sum(probs) / float(len(probs))


def log_pool_normalized(probs: list[float]) -> float:
    """Geometric-mean (normalized logarithmic) pool of binary credences."""
    if not probs:
        raise ValueError("empty panel")
    acc = 0.0
    for p in probs:
        p = min(max(p, 1e-15), 1.0 - 1e-15)
        acc += math.log(p / (1.0 - p))
    return sigmoid(acc / float(len(probs)))


def aggregates(xs: list[float], mu: float = MU, sigma: float = SIGMA, tau: float = TAU_CORRELATED) -> dict:
    probs = seat_probs(xs, mu, sigma, tau)
    true = llr_true(xs, mu, sigma, tau)
    indep = llr_indep_bayes(xs, mu, sigma, tau)
    p_true = sigmoid(true)
    p_indep = sigmoid(indep)
    p_lin = linear_pool(probs)
    p_log = log_pool_normalized(probs)
    inf = inflation_factor(len(xs), sigma, tau)
    return {
        "n": len(xs),
        "xs": list(xs),
        "seat_probs": probs,
        "p_true": p_true,
        "p_indep_bayes": p_indep,
        "p_linear": p_lin,
        "p_log_normalized": p_log,
        "llr_true": true,
        "llr_indep_bayes": indep,
        "abs_dp_indep": abs(p_indep - p_true),
        "abs_dp_linear": abs(p_lin - p_true),
        "abs_dp_log_normalized": abs(p_log - p_true),
        "logodds_inflation_factor": inf,
        "more_extreme_indep": abs(p_indep - 0.5) > abs(p_true - 0.5) + 1e-15,
    }


def draw_panel(rng: random.Random, n: int, mu: float, sigma: float, tau: float) -> tuple[int, list[float]]:
    y = 1 if rng.random() < 0.5 else 0
    z = rng.gauss(0.0, tau)
    sign = 1.0 if y == 1 else -1.0
    xs = [sign * mu + z + rng.gauss(0.0, sigma) for _ in range(n)]
    return y, xs


def monte_carlo(
    *,
    n: int = N_SEATS,
    mu: float = MU,
    sigma: float = SIGMA,
    tau: float,
    trials: int = N_TRIALS,
    seed: int = SEED,
) -> dict:
    rng = random.Random(seed)
    dp_indep = 0.0
    dp_lin = 0.0
    dp_log = 0.0
    extreme = 0
    brier_indep = 0.0
    brier_lin = 0.0
    brier_true = 0.0
    inflation_hits = 0.0
    inflation_n = 0
    for _ in range(trials):
        y, xs = draw_panel(rng, n, mu, sigma, tau)
        a = aggregates(xs, mu, sigma, tau)
        dp_indep += a["abs_dp_indep"]
        dp_lin += a["abs_dp_linear"]
        dp_log += a["abs_dp_log_normalized"]
        extreme += int(a["more_extreme_indep"])
        brier_indep += (a["p_indep_bayes"] - y) ** 2
        brier_lin += (a["p_linear"] - y) ** 2
        brier_true += (a["p_true"] - y) ** 2
        if abs(a["llr_true"]) > 0.05:
            inflation_hits += a["llr_indep_bayes"] / a["llr_true"]
            inflation_n += 1
    t = float(trials)
    analytic = inflation_factor(n, sigma, tau)
    return {
        "n": n,
        "mu": mu,
        "sigma": sigma,
        "tau": tau,
        "trials": trials,
        "seed": seed,
        "mean_abs_dp_indep": dp_indep / t,
        "mean_abs_dp_linear": dp_lin / t,
        "mean_abs_dp_log_normalized": dp_log / t,
        "frac_indep_more_extreme": extreme / t,
        "brier_indep_bayes": brier_indep / t,
        "brier_linear": brier_lin / t,
        "brier_true_posterior": brier_true / t,
        "mean_llr_ratio_indep_over_true": (inflation_hits / inflation_n) if inflation_n else None,
        "analytic_logodds_inflation": analytic,
        "pairwise_corr": (tau * tau) / (tau * tau + sigma * sigma) if (tau or sigma) else 0.0,
    }


def quantification_of(doc: dict) -> dict:
    """Find the live quantification block on a receipt or a legacy flat note."""
    if not isinstance(doc, dict):
        return {}
    nested = []
    report = doc.get("report")
    if isinstance(report, dict):
        nested.append(report.get("quantification"))
    ext = doc.get("extensions")
    if isinstance(ext, dict):
        nested.append(ext.get("quantification"))
        design = ext.get("design")
        if isinstance(design, dict):
            nested.append(design.get("quantification"))
    for candidate in (doc.get("quantification"), *nested):
        if isinstance(candidate, dict) and candidate:
            return candidate
    return {}


def canonical() -> dict:
    a = aggregates(CANONICAL_X, MU, SIGMA, TAU_CORRELATED)
    a["tau"] = TAU_CORRELATED
    a["mu"] = MU
    a["sigma"] = SIGMA
    a["note"] = (
        "Worked same-vendor panel: independence-assuming product of marginal "
        "likelihoods is more extreme than the joint posterior."
    )
    return a


def dump_fixtures() -> dict:
    dest = HERE / "fixtures"
    dest.mkdir(parents=True, exist_ok=True)
    corr = monte_carlo(tau=TAU_CORRELATED)
    indep = monte_carlo(tau=TAU_INDEPENDENT)
    can = canonical()
    (dest / "canonical-panel.json").write_text(
        json.dumps(can, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (dest / "mc-correlated.json").write_text(
        json.dumps(corr, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (dest / "mc-independent.json").write_text(
        json.dumps(indep, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {"canonical": can, "correlated": corr, "independent": indep}


def matrix_llr_true(xs: list[float], mu: float, sigma: float, tau: float) -> float:
    """Independent mechanism: explicit Sigma^{-1} via Sherman-Morrison, then 2 mu 1^T Sigma^{-1} X."""
    n = len(xs)
    sigma2, tau2 = variance_terms(sigma, tau)
    # Sigma^{-1} = sigma^{-2} I - tau^2 / (sigma^2 (sigma^2 + n tau^2)) 11^T
    s = sum(xs)
    ones_inv_x = s / (sigma2 + n * tau2)
    return 2.0 * mu * ones_inv_x


if __name__ == "__main__":
    blob = dump_fixtures()
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "xs" and kk != "seat_probs"} for k, v in blob.items()}, indent=2, sort_keys=True))
