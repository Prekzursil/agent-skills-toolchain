#!/usr/bin/env python3
"""CNF-0138 sample-size calculator.

Detect a class defect rate p at power 1-beta after confirmer false-pass
attenuation, and size n so the spec:11041 expansion rule (observed rate > tau)
actually fires with that power.

Refuses to emit n when the false-pass input is NOT-CHECKED (never assume zero).
Refuses when attenuated p_obs <= tau (power to exceed tau is then impossible).
"""
from __future__ import annotations

import math
from typing import Any

NOT_CHECKED_TOKENS = frozenset(
    {"NOT-CHECKED", "NOT_CHECKED", "UNCHECKED", "UNKNOWN", "ABSENT"}
)


class SamplingRefuse(ValueError):
    """The tool must not emit an n for this input."""


def _log_pmf(k: int, n: int, p: float) -> float:
    if k < 0 or k > n:
        return float("-inf")
    if p <= 0.0:
        return 0.0 if k == 0 else float("-inf")
    if p >= 1.0:
        return 0.0 if k == n else float("-inf")
    logc = math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
    return logc + k * math.log(p) + (n - k) * math.log(1.0 - p)


def binom_pmf(k: int, n: int, p: float) -> float:
    lp = _log_pmf(k, n, p)
    if lp == float("-inf"):
        return 0.0
    return math.exp(lp)


def binom_sf(k: int, n: int, p: float) -> float:
    """P(X >= k) for X ~ Binomial(n, p)."""
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    total = 0.0
    for i in range(k, n + 1):
        total += binom_pmf(i, n, p)
    return total


def threshold_kcrit(n: int, tau: float) -> int:
    """Smallest integer k such that k/n > tau, i.e. expand iff X >= kcrit."""
    return math.floor(n * tau) + 1


def threshold_power(n: int, p_obs: float, tau: float) -> float:
    """P(X/n > tau) = P(X >= floor(n*tau)+1)."""
    return binom_sf(threshold_kcrit(n, tau), n, p_obs)


def parse_false_pass(doc: Any) -> float:
    """Return phi in [0, 1). Refuse NOT-CHECKED or a missing/non-numeric rate."""
    if not isinstance(doc, dict):
        raise SamplingRefuse("false-pass input is not an object")
    status = str(doc.get("status") or "").strip().upper().replace("_", "-")
    rate = doc.get("rate", doc.get("false_pass_rate", doc.get("value")))
    if status in NOT_CHECKED_TOKENS:
        raise SamplingRefuse(
            "false-pass rate input is NOT-CHECKED; refusing to emit n "
            "(never assume zero)"
        )
    if isinstance(rate, str) and rate.strip().upper().replace("_", "-") in NOT_CHECKED_TOKENS:
        raise SamplingRefuse(
            "false-pass rate value is NOT-CHECKED; refusing to emit n"
        )
    if status and status != "CHECKED":
        raise SamplingRefuse(f"false-pass status is {status!r}, not CHECKED")
    if rate is None:
        raise SamplingRefuse("false-pass rate is missing")
    try:
        phi = float(rate)
    except (TypeError, ValueError) as exc:
        raise SamplingRefuse("false-pass rate is not numeric") from exc
    if not (0.0 <= phi < 1.0):
        raise SamplingRefuse(f"false-pass rate {phi} is outside [0, 1)")
    return phi


def observed_prevalence(p: float, phi: float) -> float:
    if not (0.0 < p < 1.0):
        raise SamplingRefuse(f"design defect rate p={p} is outside (0, 1)")
    if not (0.0 <= phi < 1.0):
        raise SamplingRefuse(f"false-pass phi={phi} is outside [0, 1)")
    return p * (1.0 - phi)


def n_any(p_obs: float, beta: float) -> int:
    """Smallest n with P(X>=1) >= 1-beta when X~Bin(n, p_obs). Closed form.

    n = ceil( ln(beta) / ln(1-p_obs) ), then bumped if float noise undershoots.
    Equivalent to expansion threshold tau=0 (any observed error expands).
    """
    if not (0.0 < p_obs < 1.0):
        raise SamplingRefuse(f"p_obs={p_obs} cannot drive n_any")
    if not (0.0 < beta < 1.0):
        raise SamplingRefuse(f"beta={beta} is outside (0, 1)")
    n = int(math.ceil(math.log(beta) / math.log(1.0 - p_obs)))
    n = max(n, 1)
    while (1.0 - p_obs) ** n > beta:
        n += 1
    while n > 1 and (1.0 - p_obs) ** (n - 1) <= beta:
        n -= 1
    return n


def n_min(p_obs: float, tau: float, beta: float, nmax: int = 600) -> int:
    """Smallest n with P(X/n > tau) >= 1-beta. Power is not monotone in n
    (kcrit jumps at n*tau integers), so the first hit is reported separately
    from n_stable.
    """
    if tau == 0.0:
        return n_any(p_obs, beta)
    if p_obs <= tau:
        raise SamplingRefuse(
            f"p_obs={p_obs} <= tau={tau}; cannot power a test of exceeding tau"
        )
    if not (0.0 < beta < 1.0):
        raise SamplingRefuse(f"beta={beta} is outside (0, 1)")
    target = 1.0 - beta
    for n in range(1, nmax + 1):
        if threshold_power(n, p_obs, tau) >= target:
            return n
    raise SamplingRefuse(f"no n <= {nmax} reaches power {target} at p_obs={p_obs} tau={tau}")


def n_stable(p_obs: float, tau: float, beta: float, nmax: int = 600) -> int:
    """Smallest n such that EVERY m in [n, nmax] still has power >= 1-beta.

    Operational n: drawing a few extra units must not fall into a kcrit-jump gap.
    """
    if tau == 0.0:
        return n_any(p_obs, beta)
    if p_obs <= tau:
        raise SamplingRefuse(
            f"p_obs={p_obs} <= tau={tau}; cannot power a test of exceeding tau"
        )
    target = 1.0 - beta
    ok = [threshold_power(n, p_obs, tau) >= target for n in range(1, nmax + 1)]
    if not ok[-1]:
        raise SamplingRefuse(
            f"n={nmax} still lacks power {target} at p_obs={p_obs} tau={tau}"
        )
    n = nmax
    while n > 1 and ok[n - 2]:
        n -= 1
    return n


def sizes(p: float, beta: float, phi: float, tau: float, nmax: int = 600) -> dict:
    p_obs = observed_prevalence(p, phi)
    any_n = n_any(p_obs, beta)
    if p_obs <= tau and tau > 0:
        raise SamplingRefuse(
            f"p_obs={p_obs} <= tau={tau}; refusing to emit n_min/n_stable"
        )
    min_n = n_min(p_obs, tau, beta, nmax=nmax)
    stab_n = n_stable(p_obs, tau, beta, nmax=nmax)
    kcrit = threshold_kcrit(stab_n, tau)
    return {
        "p": p,
        "beta": beta,
        "phi": phi,
        "tau": tau,
        "p_obs": p_obs,
        "n_any": any_n,
        "n_min": min_n,
        "n_stable": stab_n,
        "n": stab_n,
        "recommended": "n_stable",
        "kcrit_at_n_stable": kcrit,
        "power_at_n_min": threshold_power(min_n, p_obs, tau),
        "power_at_n_stable": threshold_power(stab_n, p_obs, tau),
        "power_at_n_any_tau0": 1.0 - (1.0 - p_obs) ** any_n,
    }


def stratum_n(stratum: dict, n_required: int) -> dict:
    pop = int(stratum["population"])
    severity = str(stratum.get("severity") or "")
    census = bool(stratum.get("census")) or severity in {"P0", "P1"}
    if pop < 0:
        raise SamplingRefuse(f"stratum {stratum.get('id')} has negative population")
    drawn = pop if census else min(n_required, pop)
    return {
        "id": stratum.get("id"),
        "severity": severity,
        "population": pop,
        "census": census,
        "n_required_uncapped": n_required,
        "n": drawn,
        "capped_at_population": (not census) and n_required > pop,
        "rule": "census-100pct" if census else "min(n_stable, population)",
    }
