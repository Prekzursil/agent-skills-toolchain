"""Retry policy: `win-arg-limit` retries EXACTLY once; nothing else retries silently."""

from __future__ import annotations

import dataclasses

import pytest

from agentspec.retry import (
    RATE_LIMIT_BASE_BACKOFF_MS,
    RATE_LIMIT_MAX_ATTEMPTS,
    RETRYABLE_ONCE,
    RetryDecision,
    plan_retry,
    rate_limit_backoff_ms,
)


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
    """ "Exactly once" is the whole point: attempt 2 must stop."""
    decision = plan_retry("win-arg-limit", attempt=2)
    assert decision.retry is False
    assert decision.next_attempt == 2
    assert "already retried" in decision.rationale


@pytest.mark.parametrize(
    "reason",
    [
        "rail-exit-137",
        "receipt-missing",
        "severed-stream",
        "timeout-1800s",
        "policy-violation",
    ],
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


def test_a_PARAMETRISED_win_arg_limit_earns_the_same_one_retry() -> None:
    """The policy matches the taxonomy MEMBER, not the whole string.

    ``win-arg-limit-34472`` (the measured payload length) is the same failure as the bare
    member, so it must get the same one retry. Before this it fell through to "no automatic
    retry" purely because of the suffix — a silent policy hole for anyone who renders detail.
    """
    assert plan_retry("win-arg-limit-34472", attempt=1).retry is True
    assert plan_retry("win-arg-limit-34472", attempt=2).retry is False


# --- rate-limited: bounded, deterministic backoff (no jitter HERE, by design) ----------------


def test_the_rate_limit_schedule_constants_are_pinned() -> None:
    """Values, not just relations — the class of hole the critic measured on the argv guard.

    5 retries mirrors ``hooks/_shared/failure_taxonomy.py``'s ``HANDLERS["429"]``
    (``action="backoff", max_retries=5``), so 6 total attempts.
    """
    assert RATE_LIMIT_MAX_ATTEMPTS == 6
    assert RATE_LIMIT_BASE_BACKOFF_MS == 1000


def test_the_backoff_doubles_and_is_a_pure_function_of_the_attempt() -> None:
    """Deterministic by construction: no clock, no entropy, so two runs are byte-identical.

    JITTER IS DELIBERATELY ABSENT. The hooks-side policy sets ``backoff=True`` meaning
    "exponential backoff with jitter", but jitter needs entropy and
    ``agentspec/determinism.py`` fails this package's own source on a ``random`` import. The
    transport shim adds jitter to the value returned here; agentspec supplies the schedule.
    """
    assert [rate_limit_backoff_ms(n) for n in range(1, 6)] == [
        1000,
        2000,
        4000,
        8000,
        16000,
    ]
    assert rate_limit_backoff_ms(3) == rate_limit_backoff_ms(3)


def test_the_backoff_refuses_a_non_positive_attempt() -> None:
    with pytest.raises(ValueError, match="attempt"):
        rate_limit_backoff_ms(0)


@pytest.mark.parametrize("reason", ["rate-limited", "rate-limited-429"])
def test_rate_limited_retries_with_a_backoff_bare_or_parametrised(reason: str) -> None:
    decision = plan_retry(reason, attempt=1)
    assert decision.retry is True
    assert decision.next_attempt == 2
    assert decision.backoff_ms == 1000
    assert "back off" in decision.rationale


def test_the_rate_limit_retry_loop_terminates_at_the_attempt_CEILING() -> None:
    """The whole point of a ceiling: a 429 must not become an unbounded retry loop.

    Asserts the total attempt count AND the schedule the loop actually waited through, so
    removing either the ceiling or the doubling turns this RED.
    """
    attempts = 0
    attempt = 1
    waited: list[int] = []
    while True:
        attempts += 1
        decision = plan_retry("rate-limited-429", attempt=attempt)
        if not decision.retry:
            assert "attempts spent" in decision.rationale
            assert decision.backoff_ms == 0
            break
        waited.append(decision.backoff_ms)
        attempt = decision.next_attempt
    assert attempts == RATE_LIMIT_MAX_ATTEMPTS
    assert waited == [1000, 2000, 4000, 8000, 16000]
    assert sum(waited) == 31_000


def test_the_backoff_is_zero_for_every_non_rate_limited_decision() -> None:
    """A consumer that sleeps ``backoff_ms`` unconditionally must not sleep on win-arg-limit."""
    assert plan_retry("win-arg-limit", attempt=1).backoff_ms == 0
    assert plan_retry("severed-stream", attempt=1).backoff_ms == 0


@pytest.mark.parametrize("bad", [1.5, True])
def test_the_decision_refuses_a_non_int_backoff(bad: object) -> None:
    """Same wire-parity rule as ``RailResult.wall_ms``: an integral float is ``1.0`` in Python
    and ``1`` in JS, one of the six measured canonicalisation divergences."""
    with pytest.raises(TypeError, match="backoff_ms"):
        RetryDecision(
            retry=False,
            next_attempt=1,
            reason="rate-limited",
            rationale="x",
            backoff_ms=bad,  # type: ignore[arg-type]
        )


def test_the_decision_refuses_a_negative_backoff() -> None:
    with pytest.raises(ValueError, match="backoff_ms"):
        RetryDecision(
            retry=False,
            next_attempt=1,
            reason="rate-limited",
            rationale="x",
            backoff_ms=-1,
        )
