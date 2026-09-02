"""Strictly proper vs improper scoring rules for CNL-0112."""
from __future__ import annotations

import math
from typing import Callable

EPS = 1e-12
Rule = Callable[[float, int], float]


def clip(q: float) -> float:
    return min(1.0 - EPS, max(EPS, float(q)))


def log_score(q: float, y: int) -> float:
    """Local strictly proper log score. Higher is better."""
    q = clip(q)
    return math.log(q) if y == 1 else math.log(1.0 - q)


def brier_score(q: float, y: int) -> float:
    """Brier (mean squared error). Lower is better; used as a bounded secondary."""
    return (float(q) - int(y)) ** 2


def linear_score(q: float, y: int) -> float:
    """Linear probability score. NOT strictly proper. Higher is better."""
    q = float(q)
    return q if y == 1 else (1.0 - q)


def expected_score(rule: Rule, q_report: float, p_true: float) -> float:
    p = float(p_true)
    return p * rule(q_report, 1) + (1.0 - p) * rule(q_report, 0)


def properness_report(p_true: float = 0.7) -> dict:
    """Calibrated report vs hedge vs extremist under log (proper) and linear (improper)."""
    cal, hedge, extreme = p_true, 0.5, 1.0
    log_cal = expected_score(log_score, cal, p_true)
    log_hedge = expected_score(log_score, hedge, p_true)
    log_ext = expected_score(log_score, extreme, p_true)
    lin_cal = expected_score(linear_score, cal, p_true)
    lin_hedge = expected_score(linear_score, hedge, p_true)
    lin_ext = expected_score(linear_score, extreme, p_true)
    brier_cal = expected_score(brier_score, cal, p_true)
    brier_hedge = expected_score(brier_score, hedge, p_true)
    return {
        "p_true": p_true,
        "reports": {"calibrated": cal, "hedge": hedge, "extremist": extreme},
        "log": {
            "calibrated": log_cal,
            "hedge": log_hedge,
            "extremist": log_ext,
            "prefers_calibrated_to_hedge": log_cal > log_hedge,
            "prefers_calibrated_to_extremist": log_cal > log_ext,
        },
        "brier_lower_better": {
            "calibrated": brier_cal,
            "hedge": brier_hedge,
            "calibrated_better_than_hedge": brier_cal < brier_hedge,
        },
        "linear_improper": {
            "calibrated": lin_cal,
            "hedge": lin_hedge,
            "extremist": lin_ext,
            "prefers_extremist_to_calibrated": lin_ext > lin_cal,
        },
        "log_is_strictly_proper_on_this_fixture": (log_cal > log_hedge)
        and (log_cal > log_ext),
        "linear_is_improper_on_this_fixture": lin_ext > lin_cal,
    }
