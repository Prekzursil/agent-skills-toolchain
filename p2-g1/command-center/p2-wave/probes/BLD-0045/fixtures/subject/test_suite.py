"""Fixture suite: covers rollback except without asserting its effect."""

from __future__ import annotations

import product as P


def test_side_effect_called_without_assert() -> None:
    P.side_effect_only(3)


def test_asserted_value_feeds_assert() -> None:
    assert P.asserted_value(3) == 4


def test_rollback_except_covered_unasserted() -> None:
    P.apply_with_rollback({"k": 1}, fail=True)


def test_rollback_happy_path_asserted() -> None:
    out = P.apply_with_rollback({"k": 1}, fail=False)
    assert out["committed"] is True


def test_partial_branch_true_arm_only() -> None:
    assert P.maybe_double(True, 5) == 10
