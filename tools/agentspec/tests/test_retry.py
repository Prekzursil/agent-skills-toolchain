"""Retry policy: `win-arg-limit` retries EXACTLY once; nothing else retries silently."""

from __future__ import annotations

import dataclasses

import pytest

from agentspec.retry import RETRYABLE_ONCE, RetryDecision, plan_retry


def test_the_retry_once_set_is_the_declared_closed_set() -> None:
    assert RETRYABLE_ONCE == ("win-arg-limit",)


def test_win_arg_limit_retries_on_the_first_attempt() -> None:
    decision = plan_retry("win-arg-limit", attempt=1)
    assert decision == RetryDecision(
        retry=True,
        next_attempt=2,
        reason="win-arg-limit",
        rationale="retry once with the prompt routed to a file/stdin",
    )


def test_win_arg_limit_does_NOT_retry_a_second_time() -> None:
    """"Exactly once" is the whole point: attempt 2 must stop."""
    decision = plan_retry("win-arg-limit", attempt=2)
    assert decision.retry is False
    assert decision.next_attempt == 2
    assert "already retried" in decision.rationale


@pytest.mark.parametrize(
    "reason",
    ["rail-exit-137", "receipt-missing", "severed-stream", "timeout-1800s", "policy-violation"],
)
def test_no_other_reason_retries(reason: str) -> None:
    decision = plan_retry(reason, attempt=1)
    assert decision.retry is False
    assert decision.rationale.startswith("no automatic retry")


def test_a_reason_outside_the_taxonomy_is_refused() -> None:
    with pytest.raises(ValueError, match="taxonomy"):
        plan_retry("mystery", attempt=1)


def test_a_non_positive_attempt_is_refused() -> None:
    with pytest.raises(ValueError, match="attempt"):
        plan_retry("win-arg-limit", attempt=0)


def test_the_decision_is_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        plan_retry("win-arg-limit", attempt=1).retry = False  # type: ignore[misc]


def test_a_retry_loop_driven_by_the_policy_terminates_after_exactly_one_retry() -> None:
    """Behavioural check, not just a table lookup: the loop must run twice, never thrice."""
    attempts = 0
    attempt = 1
    while True:
        attempts += 1
        decision = plan_retry("win-arg-limit", attempt=attempt)
        if not decision.retry:
            break
        attempt = decision.next_attempt
    assert attempts == 2
