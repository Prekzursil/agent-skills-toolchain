"""Regularized incomplete beta function and the Student t tail built on it (stdlib only).

``betainc(a, b, x)`` evaluates I_x(a, b) with the modified Lentz continued fraction
(``betacf``), switching to the symmetric form ``1 - I_{1-x}(b, a)`` once ``x`` is past the
distribution mean so the fraction converges in a few dozen terms.  ``student_t_sf`` maps a
t statistic onto it:

    P(T >= t) = 0.5 * I_{df / (df + t^2)}(df / 2, 1 / 2)      for t >= 0

which is the one-sided tail the paired test in :mod:`bench.paired_test` reports.  Everything
is plain floating point; the largest relative error against a reference table is below 1e-12
for the degrees of freedom a benchmark run produces (2 <= df <= 10^4).
"""

from __future__ import annotations

import math

MAX_ITERATIONS = 400
EPSILON = 1.0e-15
FPMIN = 1.0e-300


class IncompleteBetaError(ArithmeticError):
    """Raised when the continued fraction fails to converge or the arguments are invalid."""


def log_beta(a: float, b: float) -> float:
    """ln B(a, b) = ln G(a) + ln G(b) - ln G(a + b)."""
    if a <= 0.0 or b <= 0.0:
        raise IncompleteBetaError(f"log_beta needs a, b > 0, got a={a!r} b={b!r}")
    return math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)


def betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for I_x(a, b) (modified Lentz), valid for x < (a + 1) / (a + b + 2)."""
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < FPMIN:
        d = FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, MAX_ITERATIONS + 1):
        m2 = 2 * m
        # even step
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        h *= d * c
        # odd step
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < EPSILON:
            return h
    raise IncompleteBetaError(f"betacf did not converge for a={a!r} b={b!r} x={x!r}")


def betainc(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta I_x(a, b) for a, b > 0 and 0 <= x <= 1."""
    if not (math.isfinite(a) and math.isfinite(b) and math.isfinite(x)):
        raise IncompleteBetaError(
            f"betainc needs finite arguments, got a={a!r} b={b!r} x={x!r}"
        )
    if a <= 0.0 or b <= 0.0:
        raise IncompleteBetaError(f"betainc needs a, b > 0, got a={a!r} b={b!r}")
    if x < 0.0 or x > 1.0:
        raise IncompleteBetaError(f"betainc needs 0 <= x <= 1, got x={x!r}")
    if x == 0.0:
        return 0.0
    if x == 1.0:
        return 1.0
    front = math.exp(a * math.log(x) + b * math.log1p(-x) - log_beta(a, b))
    if x < (a + 1.0) / (a + b + 2.0):
        value = front * betacf(a, b, x) / a
    else:
        value = 1.0 - front * betacf(b, a, 1.0 - x) / b
    # the fraction is accurate to ~1e-15; clamp only rounding noise, never a real value
    if value < 0.0:
        return 0.0 if value > -1e-12 else value
    if value > 1.0:
        return 1.0 if value < 1.0 + 1e-12 else value
    return value


def student_t_sf(t: float, df: float) -> float:
    """Upper tail P(T >= t) of Student's t with ``df`` degrees of freedom."""
    if not math.isfinite(df) or df <= 0.0:
        raise IncompleteBetaError(f"student_t_sf needs df > 0, got {df!r}")
    if math.isnan(t):
        raise IncompleteBetaError("student_t_sf got t=nan")
    if math.isinf(t):
        return 0.0 if t > 0.0 else 1.0
    x = df / (df + t * t)
    tail = 0.5 * betainc(df / 2.0, 0.5, x)
    return tail if t >= 0.0 else 1.0 - tail


def student_t_cdf(t: float, df: float) -> float:
    """Lower tail P(T <= t) of Student's t with ``df`` degrees of freedom."""
    return 1.0 - student_t_sf(t, df)


def student_t_two_sided_p(t: float, df: float) -> float:
    """Two-sided p-value P(|T| >= |t|)."""
    return min(1.0, 2.0 * student_t_sf(abs(t), df))


__all__ = [
    "EPSILON",
    "FPMIN",
    "IncompleteBetaError",
    "MAX_ITERATIONS",
    "betacf",
    "betainc",
    "log_beta",
    "student_t_cdf",
    "student_t_sf",
    "student_t_two_sided_p",
]
