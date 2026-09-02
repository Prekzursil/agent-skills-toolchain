"""Budget accounting: monotonic, no double-count, totals reconcile.

Integer MICRO-units only. Floats are forbidden in the envelope — an integral float
serialises as `1.0` in Python and `1` in JS, which is one of the measured cross-runtime
canonicalisation divergences (see README "UNVERIFIED follow-up").
"""

from __future__ import annotations

import dataclasses

import pytest

from agentspec.budget import BudgetExhausted, Debit, Ledger


def test_a_fresh_ledger_has_spent_zero_and_full_remaining() -> None:
    ledger = Ledger(limit_micro=100)
    assert ledger.spent_micro == 0
    assert ledger.remaining_micro == 100
    assert ledger.exhausted is False


def test_debit_returns_a_new_ledger_and_leaves_the_old_one_untouched() -> None:
    first = Ledger(limit_micro=100)
    second = first.debit("u1", attempt=1, micro=30)
    assert first.spent_micro == 0
    assert second.spent_micro == 30
    assert second.remaining_micro == 70
    assert second.debits == (Debit(unit_id="u1", attempt=1, micro=30),)


def test_ledger_is_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        Ledger(limit_micro=1).limit_micro = 2  # type: ignore[misc]


def test_debit_is_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        Debit(unit_id="u", attempt=1, micro=1).micro = 2  # type: ignore[misc]


def test_totals_reconcile_with_the_per_debit_sum() -> None:
    ledger = Ledger(limit_micro=100).debit("u1", attempt=1, micro=10)
    ledger = ledger.debit("u1", attempt=2, micro=20).debit("u2", attempt=1, micro=5)
    assert ledger.spent_micro == sum(d.micro for d in ledger.debits) == 35


def test_spent_is_monotonic_across_a_debit_sequence() -> None:
    ledger = Ledger(limit_micro=100)
    seen = [ledger.spent_micro]
    for i, amount in enumerate((5, 1, 9), start=1):
        ledger = ledger.debit("u1", attempt=i, micro=amount)
        seen.append(ledger.spent_micro)
    assert seen == sorted(seen)
    assert seen == [0, 5, 6, 15]


def test_a_replayed_attempt_is_refused_so_a_debit_cannot_double_count() -> None:
    ledger = Ledger(limit_micro=100).debit("u1", attempt=1, micro=10)
    with pytest.raises(ValueError, match="already debited"):
        ledger.debit("u1", attempt=1, micro=10)
    assert ledger.spent_micro == 10


def test_the_same_unit_may_debit_a_different_attempt() -> None:
    ledger = Ledger(limit_micro=100).debit("u1", attempt=1, micro=10)
    assert ledger.debit("u1", attempt=2, micro=10).spent_micro == 20


@pytest.mark.parametrize("bad", [0, -1])
def test_a_non_positive_debit_is_refused(bad: int) -> None:
    with pytest.raises(ValueError, match="positive"):
        Ledger(limit_micro=100).debit("u1", attempt=1, micro=bad)


def test_a_boolean_debit_is_refused_even_though_bool_is_an_int() -> None:
    with pytest.raises(TypeError, match="int"):
        Ledger(limit_micro=100).debit("u1", attempt=1, micro=True)  # type: ignore[arg-type]


def test_a_float_debit_is_refused() -> None:
    with pytest.raises(TypeError, match="int"):
        Ledger(limit_micro=100).debit("u1", attempt=1, micro=1.5)  # type: ignore[arg-type]


def test_a_non_positive_attempt_is_refused() -> None:
    with pytest.raises(ValueError, match="attempt"):
        Ledger(limit_micro=100).debit("u1", attempt=0, micro=1)


def test_an_empty_unit_id_is_refused() -> None:
    with pytest.raises(ValueError, match="unit_id"):
        Ledger(limit_micro=100).debit("", attempt=1, micro=1)


def test_a_negative_limit_is_refused_at_construction() -> None:
    with pytest.raises(ValueError, match="limit_micro"):
        Ledger(limit_micro=-1)


def test_a_debit_landing_exactly_on_the_limit_is_allowed_and_exhausts() -> None:
    ledger = Ledger(limit_micro=10).debit("u1", attempt=1, micro=10)
    assert ledger.remaining_micro == 0
    assert ledger.exhausted is True


def test_a_debit_exceeding_the_limit_raises_budget_exhausted_with_the_taxonomy_reason() -> (
    None
):
    ledger = Ledger(limit_micro=10).debit("u1", attempt=1, micro=9)
    with pytest.raises(BudgetExhausted) as caught:
        ledger.debit("u1", attempt=2, micro=2)
    assert caught.value.reason == "budget-exhausted"
    assert caught.value.requested_micro == 2
    assert caught.value.remaining_micro == 1
    assert ledger.spent_micro == 9


def test_a_zero_limit_ledger_is_exhausted_from_the_start() -> None:
    assert Ledger(limit_micro=0).exhausted is True


def test_cost_per_successful_task_ignores_failed_attempts() -> None:
    """The benchmark metric is cost per SUCCESSFUL task, not raw token totals."""
    from agentspec.budget import cost_per_success

    ledger = Ledger(limit_micro=100).debit("u1", attempt=1, micro=10)
    ledger = ledger.debit("u1", attempt=2, micro=20).debit("u2", attempt=1, micro=6)
    assert cost_per_success(ledger, successes=2) == 18


def test_cost_per_success_is_zero_when_nothing_succeeded() -> None:
    from agentspec.budget import cost_per_success

    assert (
        cost_per_success(
            Ledger(limit_micro=10).debit("u", attempt=1, micro=5), successes=0
        )
        == 0
    )


def test_cost_per_success_refuses_a_negative_success_count() -> None:
    from agentspec.budget import cost_per_success

    with pytest.raises(ValueError, match="successes"):
        cost_per_success(Ledger(limit_micro=10), successes=-1)
