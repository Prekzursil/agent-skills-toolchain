#!/usr/bin/env python3
"""Majority / plurality error as a function of vote correlation.

Exchangeable Bernoulli votes: beta-binomial with mean competence p and
pairwise correlation rho (Boland 1989; Ladha 1992). Limits:
  rho -> 0  binomial (independent Condorcet)
  rho -> 1  all votes identical; every anonymous rule equals one voter

Four-class shared-draw mixture maps Kim et al. 2025's "agree when both
wrong" statistic to a mixing weight gamma, then to plurality error.
"""
from __future__ import annotations

import math
from typing import Iterable

RHO_GRID = tuple(round(i / 20, 2) for i in range(0, 21))
DEFAULT_N = 9
DEFAULT_P = 0.70
KIM_HELM_AGREE_BOTH_WRONG = 0.60
KIM_HELM_RANDOM_BASELINE = 1.0 / 3.0
KIM_HF_AGREE_BOTH_WRONG = 0.423
KIM_HF_RANDOM_BASELINE = 0.127
KIM_HELM_SAME_COMPANY_DELTA = 0.022


def _lbeta(a: float, b: float) -> float:
    return math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)


def _binom_pmf(k: int, n: int, p: float) -> float:
    return math.comb(n, k) * (p**k) * ((1.0 - p) ** (n - k))


def beta_binomial_pmf(k: int, n: int, p: float, rho: float) -> float:
    if n < 0 or k < 0 or k > n:
        return 0.0
    if rho <= 1e-15:
        return _binom_pmf(k, n, p)
    if rho >= 1.0 - 1e-15:
        if k == n:
            return p
        if k == 0:
            return 1.0 - p
        return 0.0
    alpha = p * (1.0 / rho - 1.0)
    beta = (1.0 - p) * (1.0 / rho - 1.0)
    logp = (
        math.lgamma(n + 1)
        - math.lgamma(k + 1)
        - math.lgamma(n - k + 1)
        + _lbeta(alpha + k, beta + n - k)
        - _lbeta(alpha, beta)
    )
    return math.exp(logp)


def _tail(n: int, p: float, rho: float, kmin: int) -> float:
    return sum(beta_binomial_pmf(k, n, p, rho) for k in range(kmin, n + 1))


def majority_accuracy(n: int, p: float, rho: float) -> float:
    if n % 2 == 0:
        raise ValueError("majority_accuracy expects odd n")
    return _tail(n, p, rho, n // 2 + 1)


def supermajority_accuracy(n: int, p: float, rho: float, frac: float = 2.0 / 3.0) -> float:
    kmin = int(math.ceil(frac * n))
    return _tail(n, p, rho, kmin)


def unanimity_accuracy(n: int, p: float, rho: float) -> float:
    return beta_binomial_pmf(n, n, p, rho)


def dictator_accuracy(p: float) -> float:
    return p


def majority_error(n: int, p: float, rho: float) -> float:
    return 1.0 - majority_accuracy(n, p, rho)


def error_row(n: int, p: float, rho: float) -> dict:
    maj = majority_error(n, p, rho)
    sup = 1.0 - supermajority_accuracy(n, p, rho)
    una = 1.0 - unanimity_accuracy(n, p, rho)
    dic = 1.0 - dictator_accuracy(p)
    return {
        "rho": rho,
        "n": n,
        "p": p,
        "majority_error": maj,
        "supermajority_2_3_error": sup,
        "unanimity_error": una,
        "random_dictator_error": dic,
        "single_voter_error": dic,
        "majority_lift_vs_single": dic - maj,
    }


def error_curve(n: int = DEFAULT_N, p: float = DEFAULT_P, grid: Iterable[float] = RHO_GRID) -> list[dict]:
    return [error_row(n, p, float(rho)) for rho in grid]


def gamma_from_agree_both_wrong(agree: float, random_baseline: float) -> float:
    """Mixture weight such that P(same wrong | both wrong) = agree.

    Shared-draw model: with probability gamma all copies share one draw;
    else independent. Then agree = gamma * 1 + (1-gamma) * random_baseline.
    """
    denom = 1.0 - random_baseline
    if denom <= 0:
        raise ValueError("random baseline must be < 1")
    g = (agree - random_baseline) / denom
    return max(0.0, min(1.0, g))


def compositions(n: int, k: int):
    if k == 1:
        yield (n,)
        return
    for i in range(n + 1):
        for rest in compositions(n - i, k - 1):
            yield (i,) + rest


def _multinomial_prob(counts: tuple[int, ...], probs: list[float]) -> float:
    n = sum(counts)
    coef = 1
    remaining = n
    for c in counts:
        coef *= math.comb(remaining, c)
        remaining -= c
    pr = float(coef)
    for c, pi in zip(counts, probs):
        pr *= pi**c
    return pr


def independent_plurality_accuracy(n: int, p: float, k: int = 4) -> float:
    """P(plurality winner is class 0) under i.i.d. Cat([p, q, ..., q]).

    Ties including the correct class are broken uniformly among the tied
    classes (so they contribute 1/len(tied)).
    """
    q = (1.0 - p) / (k - 1)
    probs = [p] + [q] * (k - 1)
    acc = 0.0
    for counts in compositions(n, k):
        pr = _multinomial_prob(counts, probs)
        mx = max(counts)
        tied = [i for i, c in enumerate(counts) if c == mx]
        if 0 in tied:
            acc += pr / len(tied)
    return acc


def mixture_plurality_accuracy(n: int, p: float, gamma: float, k: int = 4) -> float:
    """Accuracy of plurality of n copies: shared draw w.p. gamma, else independent."""
    if gamma >= 1.0 - 1e-15:
        return p
    if gamma <= 1e-15:
        return independent_plurality_accuracy(n, p, k)
    return gamma * p + (1.0 - gamma) * independent_plurality_accuracy(n, p, k)


def mixture_plurality_error(n: int, p: float, gamma: float, k: int = 4) -> float:
    return 1.0 - mixture_plurality_accuracy(n, p, gamma, k)


def ascii_curve(rows: list[dict], field: str = "majority_error") -> str:
    lines = [
        f"n={rows[0]['n']} p={rows[0]['p']}  (error vs pairwise correctness correlation rho)",
        "rho   majority  super2/3  unanimity  dictator",
    ]
    for r in rows:
        lines.append(
            f"{r['rho']:.2f}  {r['majority_error']:.4f}   "
            f"{r['supermajority_2_3_error']:.4f}   "
            f"{r['unanimity_error']:.4f}     "
            f"{r['random_dictator_error']:.4f}"
        )
    _ = field
    return "\n".join(lines)


def rounded_curve(rows: list[dict], ndigits: int = 12) -> list[dict]:
    out = []
    for r in rows:
        item = {}
        for k, v in r.items():
            if isinstance(v, float):
                item[k] = round(v, ndigits)
            else:
                item[k] = v
        out.append(item)
    return out


def kim_gamma_helm() -> float:
    return gamma_from_agree_both_wrong(
        KIM_HELM_AGREE_BOTH_WRONG, KIM_HELM_RANDOM_BASELINE
    )


def kim_gamma_helm_same_company() -> float:
    agree = KIM_HELM_AGREE_BOTH_WRONG + KIM_HELM_SAME_COMPANY_DELTA
    return gamma_from_agree_both_wrong(agree, KIM_HELM_RANDOM_BASELINE)


def self_check() -> None:
    n, p = DEFAULT_N, DEFAULT_P
    e0 = majority_error(n, p, 0.0)
    e1 = majority_error(n, p, 1.0)
    single = 1.0 - p
    assert e0 < single - 1e-9, (e0, single)
    assert abs(e1 - single) < 1e-9, (e1, single)
    prev = -1.0
    for rho in RHO_GRID:
        e = majority_error(n, p, rho)
        assert e + 1e-9 >= prev, (rho, e, prev)
        prev = e
    g = kim_gamma_helm()
    # 0.6 = g*1 + (1-g)/3  => g = 0.4
    assert abs(g - 0.4) < 1e-9, g
    acc_id = mixture_plurality_accuracy(n, p, 1.0)
    assert abs(acc_id - p) < 1e-12
    acc_ind = independent_plurality_accuracy(5, 0.7, 4)
    assert 0.7 < acc_ind < 1.0


if __name__ == "__main__":
    self_check()
    rows = error_curve()
    print(ascii_curve(rows))
    print("gamma_helm", kim_gamma_helm())
    print("SUCCESS:RES-0078-curve-self-check")
