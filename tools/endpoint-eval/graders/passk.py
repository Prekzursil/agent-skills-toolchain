"""pass@k, pass^k and the keep / discard / crash / insufficient decision table.

``pass_at_k`` is the Chen et al. (2021) unbiased estimator ``1 - C(n-c, k) / C(n, k)``
(capability: at least one of k trials succeeds). ``pass_hat_k`` is the tau-bench pass^k
``C(c, k) / C(n, k)`` (reliability: ALL k trials succeed). Both are exact via ``math.comb``.

Decision table (lens 08 section 4, BUILD-WAVE-PROPOSAL WU-4): a 429/5xx-marked run is a
``crash``; fewer than ``min_n`` trials is ``insufficient`` (neither keep nor discard); otherwise
``keep`` iff pass@3 meets the tier target (T2 local 0.90, T3 hosted 0.80) and, when a
reliability gate applies, pass^3 == 1.00; else ``discard``.
"""

from __future__ import annotations

from math import comb

KEEP = "keep"
DISCARD = "discard"
CRASH = "crash"
INSUFFICIENT = "insufficient"
DECISIONS = (KEEP, DISCARD, CRASH, INSUFFICIENT)

T2_PASS_AT_3 = 0.90
T3_PASS_AT_3 = 0.80
RELIABILITY_PASS_HAT_3 = 1.00
DEFAULT_MIN_N = 4
_TOLERANCE = 1e-9


def _check(n: int, c: int, k: int) -> None:
    if n < 1:
        raise ValueError(f"n must be >= 1, got {n}")
    if not 0 <= c <= n:
        raise ValueError(f"c must be in 0..n, got c={c} n={n}")
    if not 1 <= k <= n:
        raise ValueError(f"k must be in 1..n, got k={k} n={n}")


def pass_at_k(n: int, c: int, k: int) -> float:
    """P(at least one success among k draws) from n trials with c successes."""
    _check(n, c, k)
    if n - c < k:
        return 1.0
    return 1.0 - comb(n - c, k) / comb(n, k)


def pass_hat_k(n: int, c: int, k: int) -> float:
    """P(all k draws succeed) from n trials with c successes (tau-bench pass^k)."""
    _check(n, c, k)
    return comb(c, k) / comb(n, k)


def meets(target: float, value: float) -> bool:
    return value + _TOLERANCE >= target


def decision(
    pass_at_1: float,
    pass_at_3: float,
    pass_hat_3: float,
    n: int,
    min_n: int = DEFAULT_MIN_N,
    *,
    crashed: bool = False,
    pass_at_3_target: float = T2_PASS_AT_3,
    pass_hat_3_target: float | None = RELIABILITY_PASS_HAT_3,
    pass_at_1_target: float | None = None,
) -> str:
    if crashed:
        return CRASH
    if n < min_n:
        return INSUFFICIENT
    if not meets(pass_at_3_target, pass_at_3):
        return DISCARD
    if pass_hat_3_target is not None and not meets(pass_hat_3_target, pass_hat_3):
        return DISCARD
    if pass_at_1_target is not None and not meets(pass_at_1_target, pass_at_1):
        return DISCARD
    return KEEP
