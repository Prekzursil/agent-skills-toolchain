#!/usr/bin/env python3
"""Sample-size (power) calculator for RES-0095.

Paired z-test for a mean per-case difference (TST-0298's paired analysis):

    n = ceil( (z_{1-α/2} + z_{1-β})^2 * σ_d^2 / δ^2 )

σ_d^2 is the variance of the per-case paired difference. For a binary
pass/fail metric with unknown pairing correlation we use the conservative
unpaired sum of Bernoulli variances, then add twice the RES-0094 residual
(measurement-error variance on each arm).

The intended effect size δ is an ASSUMPTION. It is never read from a
measured improvement on this tree.
"""
from __future__ import annotations

import math
from statistics import NormalDist
from typing import Any, Callable

ALPHA = 0.05
POWER = 0.80
# Conventional two-sided 80% power. Also recomputed live via NormalDist.
Z_A_HARD = 1.959963984540054  # Φ^{-1}(0.975)
Z_B_HARD = 0.841621233572914  # Φ^{-1}(0.80)

# Primary assumed improvement: 10 percentage points. The only numeric
# "improvement" magnitude this program names is TST-0298's synthetic
# 10-point known-effect control. Using it here is still an assumption,
# not a measurement of this estate's agents.
ASSUMED_DELTA = 0.10
ASSUMED_P0 = 0.50  # max Bernoulli variance; no live baseline pass-rate
SHERMAN_KENT_BAND = "roughly even"
SHERMAN_KENT_P_INTERVAL = (0.40, 0.60)
DELTA_ENVELOPE = (0.05, 0.20)


def z_alpha_beta(alpha: float = ALPHA, power: float = POWER) -> tuple[float, float]:
    nd = NormalDist()
    z_a = nd.inv_cdf(1.0 - alpha / 2.0)
    z_b = nd.inv_cdf(power)
    return z_a, z_b


def k_factor(alpha: float = ALPHA, power: float = POWER) -> float:
    z_a, z_b = z_alpha_beta(alpha, power)
    return (z_a + z_b) ** 2


def bernoulli_diff_variance(p0: float, delta: float) -> float:
    """Conservative unpaired Var(Y-X) for two Bernoulli arms."""
    if not 0.0 <= p0 <= 1.0:
        raise ValueError(f"p0 out of range: {p0}")
    p1 = p0 + delta
    if not 0.0 <= p1 <= 1.0:
        raise ValueError(f"p0+delta out of range: p0={p0} delta={delta}")
    return p0 * (1.0 - p0) + p1 * (1.0 - p1)


def compose_sigma2(
    p0: float, delta: float, residual_variance: float
) -> dict[str, float]:
    outcome = bernoulli_diff_variance(p0, delta)
    meas = 2.0 * max(0.0, float(residual_variance))
    return {
        "bernoulli_unpaired": outcome,
        "measurement_error_both_arms": meas,
        "sigma2": outcome + meas,
    }


def required_n(
    delta: float,
    sigma2: float,
    alpha: float = ALPHA,
    power: float = POWER,
) -> int:
    if delta == 0:
        raise ValueError("effect size δ=0 is not estimable; refuse n")
    if delta < 0:
        raise ValueError("effect size must be positive")
    if sigma2 < 0:
        raise ValueError("variance must be >= 0")
    if sigma2 == 0:
        raise ValueError(
            "σ²=0 would claim n=1; refuse residual-only-zero without an outcome model"
        )
    raw = k_factor(alpha, power) * sigma2 / (delta**2)
    return int(math.ceil(raw - 1e-12))


def required_n_from_printed(
    z_a: float, z_b: float, sigma2: float, delta: float
) -> int:
    """Independent arithmetic path used by the reviewer (no k_factor())."""
    if delta <= 0:
        raise ValueError("delta must be > 0")
    raw = ((z_a + z_b) ** 2) * sigma2 / (delta**2)
    return int(math.ceil(raw - 1e-12))


def required_n_broken_constant(
    delta: float,
    sigma2: float,
    alpha: float = ALPHA,
    power: float = POWER,
    constant: int = 240,
) -> int:
    """Known-broken calculator: ignores δ. Must NOT be used for the artifact."""
    _ = (delta, sigma2, alpha, power)
    return int(constant)


def classify(required: int, planned: int) -> dict[str, Any]:
    if planned < required:
        verdict = "UNDERPOWERED"
        shortfall = required - planned
        surplus = 0
    else:
        verdict = "ADEQUATE"
        shortfall = 0
        surplus = planned - required
    return {
        "required_n": required,
        "planned_n": planned,
        "verdict": verdict,
        "shortfall": shortfall,
        "surplus": surplus,
        "printed": (
            f"required_n={required} planned_n={planned} "
            f"comparison={verdict} shortfall={shortfall} surplus={surplus}"
        ),
    }


def sensitivity_halved(
    delta: float,
    p0: float,
    residual_variance: float,
    planned_n: int,
    calc: Callable[..., int] | None = None,
) -> dict[str, Any]:
    fn = calc or required_n
    d_half = delta / 2.0
    sig_full = compose_sigma2(p0, delta, residual_variance)
    sig_half = compose_sigma2(p0, d_half, residual_variance)
    n_full = fn(delta, sig_full["sigma2"])
    n_half = fn(d_half, sig_half["sigma2"])
    moved = n_half > n_full
    ratio = (n_half / n_full) if n_full else None
    return {
        "delta": delta,
        "delta_halved": d_half,
        "sigma2_full": sig_full["sigma2"],
        "sigma2_halved": sig_half["sigma2"],
        "required_n": n_full,
        "required_n_halved": n_half,
        "moved": moved,
        "ratio": ratio,
        "printed": (
            f"delta={delta} required_n={n_full} ; "
            f"delta_halved={d_half} required_n={n_half} "
            f"ratio={ratio} moved={moved}"
        ),
        "planned_n": planned_n,
        "full_vs_planned": classify(n_full, planned_n),
        "halved_vs_planned": classify(n_half, planned_n),
    }


def report(
    planned_n: int,
    residual_variance: float,
    delta: float = ASSUMED_DELTA,
    p0: float = ASSUMED_P0,
    alpha: float = ALPHA,
    power: float = POWER,
) -> dict[str, Any]:
    z_a, z_b = z_alpha_beta(alpha, power)
    composed = compose_sigma2(p0, delta, residual_variance)
    n = required_n(delta, composed["sigma2"], alpha, power)
    n_hard = required_n_from_printed(Z_A_HARD, Z_B_HARD, composed["sigma2"], delta)
    n_reviewer = required_n_from_printed(z_a, z_b, composed["sigma2"], delta)
    if n != n_reviewer:
        raise RuntimeError(f"reviewer arithmetic drifted: n={n} reviewer={n_reviewer}")
    cmp_ = classify(n, planned_n)
    sens = sensitivity_halved(delta, p0, residual_variance, planned_n)
    broken = sensitivity_halved(
        delta, p0, residual_variance, planned_n, calc=required_n_broken_constant
    )
    # Optimistic row (not the primary claim).
    opt_p0 = 0.80
    try:
        opt_sig = compose_sigma2(opt_p0, delta, residual_variance)
        opt_n = required_n(delta, opt_sig["sigma2"], alpha, power)
        opt_cmp = classify(opt_n, planned_n)
    except ValueError:
        opt_n, opt_cmp, opt_sig = None, None, None
    return {
        "alpha": alpha,
        "power": power,
        "z_a": z_a,
        "z_b": z_b,
        "z_a_hard": Z_A_HARD,
        "z_b_hard": Z_B_HARD,
        "k": (z_a + z_b) ** 2,
        "p0_assumed": p0,
        "delta_assumed": delta,
        "p1_assumed": p0 + delta,
        "residual_variance": residual_variance,
        "variance_parts": composed,
        "required_n": n,
        "required_n_hardcoded_z": n_hard,
        "required_n_reviewer_arithmetic": n_reviewer,
        "hardcoded_z_agrees": n == n_hard,
        "comparison": cmp_,
        "sensitivity_halved_effect_size": sens,
        "known_broken_constant_calculator": broken,
        "optimistic_p0_0_80": {
            "p0": opt_p0,
            "sigma2": None if opt_sig is None else opt_sig["sigma2"],
            "required_n": opt_n,
            "comparison": opt_cmp,
            "note": (
                "Not the primary claim. High baseline pass-rate reduces Bernoulli "
                "variance; included so a reader can see that 'adequate' is reachable "
                "only under a more optimistic p0 than we are willing to assume."
            ),
        },
        "formula": (
            "n = ceil((z_{1-α/2} + z_{1-β})^2 * σ_d^2 / δ^2) ; "
            "σ_d^2 = p0(1-p0)+p1(1-p1) + 2*σ_residual^2  (paired z, conservative unpaired Bernoulli)"
        ),
    }
