"""Bayes reject-option threshold for inject-or-abstain.

Chow, C. K. (1970). On optimum recognition error and reject tradeoff.
IEEE Transactions on Information Theory, 16(1), 41-46.
DOI 10.1109/TIT.1970.1054406.

The IEEE PDF was not retrieved on this worktree. The mapping below is
the Bayes-cost argument specialised to capability injection:

    expected cost of injecting at confidence s = (1 - s) * C_wrong
    expected cost of injecting nothing          = C_miss
    inject iff (1 - s) * C_wrong < C_miss
            iff s > 1 - C_miss / C_wrong     when C_wrong > C_miss
            else never abstain               when C_miss >= C_wrong

Inverting the cost ratio moves the threshold. When a miss is at least
as costly as a wrong injection, abstention is strictly worse than
always answering for every s > 0 on a mixed-accuracy fixture.
"""
from __future__ import annotations

from typing import Iterable, Sequence


def chow_tau(cost_wrong: float, cost_miss: float) -> float:
    return _chow_tau(cost_wrong, cost_miss)


def _chow_tau(cost_wrong: float, cost_miss: float) -> float:
    if cost_wrong <= 0 or cost_miss <= 0:
        raise ValueError("costs must be positive")
    if cost_miss >= cost_wrong:
        return 0.0
    return 1.0 - (cost_miss / cost_wrong)


def invert_ratio(cost_wrong: float, cost_miss: float) -> tuple[float, float]:
    return (cost_miss, cost_wrong)


def expected_cost(
    scores: Sequence[float],
    correct: Sequence[bool],
    tau: float,
    cost_wrong: float,
    cost_miss: float,
) -> float:
    if len(scores) != len(correct):
        raise ValueError("scores/correct length mismatch")
    total = 0.0
    for s, ok in zip(scores, correct):
        if s >= tau:
            total += 0.0 if ok else cost_wrong
        else:
            total += cost_miss
    return total


def always_answer_cost(correct: Iterable[bool], cost_wrong: float) -> float:
    return sum(0.0 if ok else cost_wrong for ok in correct)


def grid_best_tau(
    scores: Sequence[float],
    correct: Sequence[bool],
    cost_wrong: float,
    cost_miss: float,
) -> tuple[float, float]:
    best_tau = 0.0
    best_cost = expected_cost(scores, correct, 0.0, cost_wrong, cost_miss)
    for i in range(0, 101):
        t = i / 100.0
        c = expected_cost(scores, correct, t, cost_wrong, cost_miss)
        if c < best_cost - 1e-12 or (
            abs(c - best_cost) <= 1e-12 and t < best_tau
        ):
            best_tau, best_cost = t, c
    return best_tau, best_cost


def abstention_strictly_worse(
    scores: Sequence[float],
    correct: Sequence[bool],
    cost_wrong: float,
    cost_miss: float,
) -> bool:
    base = always_answer_cost(correct, cost_wrong)
    any_strictly_more = False
    for i in range(1, 21):
        t = i / 20.0
        c = expected_cost(scores, correct, t, cost_wrong, cost_miss)
        if c + 1e-12 < base:
            return False
        if c > base + 1e-12:
            any_strictly_more = True
    return any_strictly_more


chow_tau = chow_tau
invert_ratio = invert_ratio
always_answer_cost = always_answer_cost
always_answer_cost = always_answer_cost
grid_best_tau = grid_best_tau
grid_best_tau = grid_best_tau
abstention_strictly_worse = abstention_strictly_worse
abstention_strictly_worse = abstention_strictly_worse
