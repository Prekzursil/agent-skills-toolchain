"""Author missed-defect bound: hypergeometric zero-defect 95% upper bound.

Population unknown => NOT-COMPUTABLE. Never emit a confidence number without N.
Implementation: iterative product P(X=0)=Π (N-K-i)/(N-i), binary search on K.
"""
from __future__ import annotations

from typing import Any

NOT_COMPUTABLE = "NOT-COMPUTABLE"
ALPHA_95 = 0.05


def hypergeometric_p_zero(population: int, defective: int, sample: int) -> float:
    if sample == 0:
        return 1.0
    if population < 0 or sample < 0 or defective < 0:
        return 0.0
    if sample > population:
        return 0.0
    if defective > population - sample:
        return 0.0
    p = 1.0
    for i in range(sample):
        p *= (population - defective - i) / (population - i)
    return p


def upper_defective_count(population: int, sample: int, alpha: float = ALPHA_95) -> int:
    """Largest K such that P(observe 0 defects) >= alpha."""
    if sample == population:
        return 0
    lo, hi = 0, population - sample
    best = 0
    while lo <= hi:
        mid = (lo + hi) // 2
        if hypergeometric_p_zero(population, mid, sample) >= alpha:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def missed_defect_bound_95(
    population: Any,
    sample: Any,
    observed_defects: int = 0,
    alpha: float = ALPHA_95,
) -> dict[str, Any]:
    """95% hypergeometric upper bound on population defect rate given observed defects.

    Only the zero-defect case is required by BLD-0062 ('could have missed').
    Non-zero observed_defects is rejected rather than approximated: this engine
    does not invent a confidence number it cannot compute exactly.
    """
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
    k = upper_defective_count(n_pop, n_samp, alpha)
    return {
        "status": "COMPUTED",
        "alpha": alpha,
        "population": n_pop,
        "sample": n_samp,
        "observed_defects": 0,
        "defective_count_upper": k,
        "rate": k / n_pop,
        "remainder_worst_case_rate": (n_pop - n_samp) / n_pop,
        "method": "hypergeometric-zero-defect-upper-bound-product",
        "p_zero_at_k": hypergeometric_p_zero(n_pop, k, n_samp),
    }
