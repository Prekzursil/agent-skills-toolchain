"""Independent reviewer bound: same estimand, different calculator.

Uses math.lgamma log-combinatorics and a linear scan on K instead of the
author's iterative product + binary search. Agreement is the review.
"""
from __future__ import annotations

import math
from typing import Any

NOT_COMPUTABLE = "NOT-COMPUTABLE"
ALPHA_95 = 0.05


def log_comb(n: int, k: int) -> float:
    if k < 0 or k > n:
        return float("-inf")
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def hypergeometric_p_zero(population: int, defective: int, sample: int) -> float:
    if sample == 0:
        return 1.0
    if population < 0 or sample < 0 or defective < 0:
        return 0.0
    if sample > population:
        return 0.0
    if defective > population - sample:
        return 0.0
    return math.exp(
        log_comb(population - defective, sample) - log_comb(population, sample)
    )


def missed_defect_bound_95(
    population: Any,
    sample: Any,
    observed_defects: int = 0,
    alpha: float = ALPHA_95,
) -> dict[str, Any]:
    if population is None or sample is None:
        return {
            "status": NOT_COMPUTABLE,
            "reason": "population-or-sample-unknown",
            "alpha": alpha,
        }
    try:
        n_pop = int(population)
        n_samp = int(sample)
        n_obs = int(observed_defects)
    except (TypeError, ValueError):
        return {
            "status": NOT_COMPUTABLE,
            "reason": "non-integer-inputs",
            "alpha": alpha,
        }
    if n_pop <= 0 or n_samp < 0:
        return {
            "status": NOT_COMPUTABLE,
            "reason": "non-positive-population-or-negative-sample",
            "alpha": alpha,
            "population": n_pop,
            "sample": n_samp,
        }
    if n_samp > n_pop:
        return {
            "status": NOT_COMPUTABLE,
            "reason": "sample-exceeds-population",
            "alpha": alpha,
            "population": n_pop,
            "sample": n_samp,
        }
    if n_obs != 0:
        return {
            "status": NOT_COMPUTABLE,
            "reason": "nonzero-observed-defects-not-supported-by-zero-defect-engine",
            "alpha": alpha,
            "population": n_pop,
            "sample": n_samp,
            "observed_defects": n_obs,
        }
    if n_samp == n_pop:
        k = 0
    else:
        k = 0
        for cand in range(0, n_pop - n_samp + 1):
            if hypergeometric_p_zero(n_pop, cand, n_samp) >= alpha:
                k = cand
            else:
                break
    return {
        "status": "COMPUTED",
        "alpha": alpha,
        "population": n_pop,
        "sample": n_samp,
        "observed_defects": 0,
        "defective_count_upper": k,
        "rate": k / n_pop,
        "remainder_worst_case_rate": (n_pop - n_samp) / n_pop,
        "method": "hypergeometric-zero-defect-upper-bound-lgamma-linear",
        "p_zero_at_k": hypergeometric_p_zero(n_pop, k, n_samp),
    }


def bounds_match(author: dict[str, Any], reviewer: dict[str, Any]) -> bool:
    if author.get("status") != reviewer.get("status"):
        return False
    if author.get("status") == NOT_COMPUTABLE:
        return True
    return (
        int(author["defective_count_upper"]) == int(reviewer["defective_count_upper"])
        and int(author["population"]) == int(reviewer["population"])
        and int(author["sample"]) == int(reviewer["sample"])
        and abs(float(author["rate"]) - float(reviewer["rate"])) < 1e-12
    )
