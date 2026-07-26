"""The failure taxonomy is CLOSED, and every member must be producible."""

from __future__ import annotations

import pytest

from agentspec import taxonomy


def test_taxonomy_is_the_exact_closed_set() -> None:
    """A frozen enumeration: adding or removing a member is a deliberate diff."""
    assert taxonomy.REASONS == (
        "budget-exhausted",
        "env-missing",
        "policy-violation",
        "progress-stream",
        "rail-exit",
        "receipt-empty",
        "receipt-incomplete",
        "receipt-missing",
        "receipt-unparseable",
        "schema-invalid",
        "severed-stream",
        "spawn-failed",
        "timeout",
        "win-arg-limit",
    )


def test_reasons_are_sorted_and_unique() -> None:
    assert list(taxonomy.REASONS) == sorted(set(taxonomy.REASONS))


def test_is_reason_accepts_a_bare_member() -> None:
    assert taxonomy.is_reason("receipt-empty") is True


def test_is_reason_accepts_a_parametrised_member() -> None:
    assert taxonomy.is_reason("rail-exit-3") is True
    assert taxonomy.is_reason("timeout-1800s") is True
    assert taxonomy.is_reason("env-missing-XAI_API_KEY") is True


def test_is_reason_rejects_an_unknown_code() -> None:
    assert taxonomy.is_reason("kaboom") is False


def test_is_reason_rejects_a_prefix_that_is_not_a_full_segment() -> None:
    """`rail-exiting` shares a prefix with `rail-exit` but is NOT a member."""
    assert taxonomy.is_reason("rail-exiting") is False


def test_is_reason_rejects_an_empty_code() -> None:
    assert taxonomy.is_reason("") is False


def test_rail_exit_renders_the_exit_code() -> None:
    assert taxonomy.rail_exit(137) == "rail-exit-137"
    assert taxonomy.is_reason(taxonomy.rail_exit(137)) is True


def test_timeout_renders_seconds() -> None:
    assert taxonomy.timeout(1800) == "timeout-1800s"
    assert taxonomy.is_reason(taxonomy.timeout(1800)) is True


def test_env_missing_renders_the_variable_name() -> None:
    assert taxonomy.env_missing("XAI_API_KEY") == "env-missing-XAI_API_KEY"


def test_rail_exit_refuses_a_zero_exit_code() -> None:
    """exit 0 is never a rail-exit failure — it is SEVERED or SUCCESS."""
    with pytest.raises(ValueError, match="exit 0"):
        taxonomy.rail_exit(0)


def test_timeout_refuses_a_non_positive_budget() -> None:
    with pytest.raises(ValueError, match="positive"):
        taxonomy.timeout(0)


def test_env_missing_refuses_an_empty_name() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        taxonomy.env_missing("")
