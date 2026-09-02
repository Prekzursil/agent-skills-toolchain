"""Paired t-test on matched per-case benchmark scores (TST-0299).

Every candidate workflow is scored on the same benchmark cases as the baseline, so the unit
of analysis is the per-case difference ``d_i = candidate_i - baseline_i``.  The statistic is
``t = mean(d) / (sd(d) / sqrt(n))`` on ``n - 1`` degrees of freedom and the one-sided
p-value ``P(T >= t)`` answers the question a certification gate asks - is the candidate
*better* than the baseline, not merely different.

Degenerate difference vectors are decided explicitly instead of dividing by zero: a
candidate identical to the baseline has no evidence at all (``p = 1.0``), a constant
positive shift on every case is as strong as evidence gets (``p = 0.0``).
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Sequence

from .incbeta import student_t_sf, student_t_two_sided_p

MIN_PAIRS = 2


class PairedTestError(ValueError):
    """Raised when the two score vectors cannot be paired."""


def differences(baseline: Sequence[float], candidate: Sequence[float]) -> list[float]:
    """Per-case ``candidate - baseline`` differences; the vectors must pair up exactly."""
    if len(baseline) != len(candidate):
        raise PairedTestError(
            f"baseline has {len(baseline)} cases but candidate has {len(candidate)}; "
            "scores must be matched case by case"
        )
    if len(baseline) < MIN_PAIRS:
        raise PairedTestError(
            f"a paired test needs at least {MIN_PAIRS} cases, got {len(baseline)}"
        )
    out: list[float] = []
    for idx, (b, c) in enumerate(zip(baseline, candidate)):
        if isinstance(b, bool) or isinstance(c, bool):
            raise PairedTestError(f"case {idx}: boolean score is not a number")
        try:
            fb, fc = float(b), float(c)
        except (TypeError, ValueError) as exc:
            raise PairedTestError(f"case {idx}: non-numeric score {b!r}/{c!r}") from exc
        if not (math.isfinite(fb) and math.isfinite(fc)):
            raise PairedTestError(f"case {idx}: non-finite score {b!r}/{c!r}")
        out.append(fc - fb)
    return out


@dataclass(frozen=True)
class PairedTResult:
    """Everything a reviewer needs to recompute the verdict from raw scores."""

    n: int
    df: int
    mean_diff: float
    sd_diff: float
    se_diff: float
    t_stat: float
    p_greater: float
    p_less: float
    p_two_sided: float
    degenerate: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sample_sd(values: Sequence[float], mean: float) -> float:
    n = len(values)
    ss = math.fsum((v - mean) ** 2 for v in values)
    return math.sqrt(ss / (n - 1))


def paired_t_test(
    baseline: Sequence[float], candidate: Sequence[float]
) -> PairedTResult:
    """Paired Student t-test of ``candidate`` against ``baseline`` on matched cases."""
    d = differences(baseline, candidate)
    n = len(d)
    df = n - 1
    mean = math.fsum(d) / n
    sd = _sample_sd(d, mean)
    # differences that are all equal to within floating-point noise: no spread to test against
    if sd <= 1e-15 * max(1.0, abs(mean)):
        if mean > 0.0:
            t, p_gt, p_lt, p2 = math.inf, 0.0, 1.0, 0.0
        elif mean < 0.0:
            t, p_gt, p_lt, p2 = -math.inf, 1.0, 0.0, 0.0
        else:
            t, p_gt, p_lt, p2 = 0.0, 1.0, 1.0, 1.0
        return PairedTResult(n, df, mean, 0.0, 0.0, t, p_gt, p_lt, p2, True)
    se = sd / math.sqrt(n)
    t = mean / se
    p_gt = student_t_sf(t, df)
    p_lt = student_t_sf(-t, df)
    p2 = student_t_two_sided_p(t, df)
    return PairedTResult(n, df, mean, sd, se, t, p_gt, p_lt, p2, False)


def paired_mean_greater_p(
    baseline: Sequence[float], candidate: Sequence[float]
) -> float:
    """One-sided p-value for H1: the candidate's mean per-case score exceeds the baseline's."""
    return paired_t_test(baseline, candidate).p_greater


def paired_two_sided_p(baseline: Sequence[float], candidate: Sequence[float]) -> float:
    """Two-sided p-value for H1: the candidate's mean per-case score differs from the baseline's."""
    return paired_t_test(baseline, candidate).p_two_sided


__all__ = [
    "MIN_PAIRS",
    "PairedTResult",
    "PairedTestError",
    "differences",
    "paired_mean_greater_p",
    "paired_t_test",
    "paired_two_sided_p",
]
