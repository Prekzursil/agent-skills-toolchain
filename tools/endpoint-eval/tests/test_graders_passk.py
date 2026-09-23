"""pass@k (Chen et al.), pass^k (tau-bench) and the keep/discard/crash/insufficient table."""

from __future__ import annotations

import pytest
from graders.passk import (
    CRASH,
    DISCARD,
    INSUFFICIENT,
    KEEP,
    T2_PASS_AT_3,
    T3_PASS_AT_3,
    decision,
    meets,
    pass_at_k,
    pass_hat_k,
)


def test_pass_at_k_hand_computed() -> None:
    assert pass_at_k(5, 2, 1) == pytest.approx(0.4)
    assert pass_at_k(5, 2, 3) == pytest.approx(0.9)
    assert pass_at_k(4, 0, 3) == 0.0
    assert pass_at_k(4, 4, 3) == 1.0
    assert pass_at_k(4, 2, 3) == 1.0  # n - c < k: every k-subset contains a success


def test_pass_at_k_is_exact_not_floating_drift() -> None:
    assert pass_at_k(10, 3, 5) == 1 - (21 / 252)


def test_pass_hat_k_hand_computed() -> None:
    assert pass_hat_k(4, 4, 3) == 1.0
    assert pass_hat_k(4, 3, 3) == pytest.approx(0.25)
    assert pass_hat_k(4, 2, 3) == 0.0
    assert pass_hat_k(5, 5, 1) == 1.0


def test_pass_hat_1_equals_pass_at_1() -> None:
    for n, c in ((5, 2), (4, 3), (8, 8), (8, 0)):
        assert pass_hat_k(n, c, 1) == pytest.approx(pass_at_k(n, c, 1))


@pytest.mark.parametrize(
    "bad", [(0, 0, 1), (4, 5, 1), (4, 2, 0), (4, 2, 5), (4, -1, 1)]
)
def test_estimators_reject_invalid_inputs(bad: tuple[int, int, int]) -> None:
    with pytest.raises(ValueError):
        pass_at_k(*bad)
    with pytest.raises(ValueError):
        pass_hat_k(*bad)


def test_meets_with_tolerance() -> None:
    assert meets(0.90, 0.90)
    assert meets(0.90, 0.95)
    assert meets(0.90, 0.9 - 1e-12)
    assert not meets(0.90, 0.89)
    assert T2_PASS_AT_3 == 0.90
    assert T3_PASS_AT_3 == 0.80


def test_decision_table_rows() -> None:
    assert decision(1.0, 1.0, 1.0, n=4) == KEEP
    assert decision(0.5, 0.9, 1.0, n=4) == KEEP
    assert decision(0.5, 0.9, 0.25, n=4) == DISCARD
    assert decision(0.25, 0.75, 0.0, n=4) == DISCARD
    assert decision(1.0, 1.0, 1.0, n=3) == INSUFFICIENT
    assert decision(1.0, 1.0, 1.0, n=3, min_n=3) == KEEP
    assert decision(1.0, 1.0, 1.0, n=4, crashed=True) == CRASH
    assert decision(1.0, 1.0, 1.0, n=0, crashed=True) == CRASH


def test_decision_hosted_tier_target_and_reliability_toggle() -> None:
    assert (
        decision(
            0.5, 0.85, 0.5, n=4, pass_at_3_target=T3_PASS_AT_3, pass_hat_3_target=None
        )
        == KEEP
    )
    assert (
        decision(
            0.5, 0.85, 0.5, n=4, pass_at_3_target=T2_PASS_AT_3, pass_hat_3_target=None
        )
        == DISCARD
    )
    assert decision(0.0, 0.9, 1.0, n=4, pass_at_1_target=0.5) == DISCARD
    assert decision(0.75, 0.9, 1.0, n=4, pass_at_1_target=0.5) == KEEP
