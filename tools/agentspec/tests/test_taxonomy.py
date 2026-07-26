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
        "rate-limited",
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


# --- rate-limited: the member a lane-4 adapter could not render without editing agentspec ---


def test_rate_limited_renders_the_http_status() -> None:
    """MEASURED GAP: the closed set had no rate-limit member.

    A 429 is frequent on this box (two subscriptions, a nightly fan-out), and
    ``terminal.failure_line``, ``retry.plan_retry`` and ``envelope.validate_observation`` all
    REJECT a non-member — so an adapter that hit one could not render a terminal marker or an
    envelope error code at all. The repo's pre-existing ``hooks/_shared/failure_taxonomy.py``
    labels the same class ``"429"``; the mapping is documented in the package README.
    """
    assert taxonomy.rate_limited(429) == "rate-limited-429"
    assert taxonomy.rate_limited(529) == "rate-limited-529"
    assert taxonomy.is_reason(taxonomy.rate_limited(429)) is True


def test_rate_limited_refuses_a_status_that_is_not_an_error() -> None:
    """``rate-limited-200`` is nonsense; the renderer must not mint it."""
    with pytest.raises(ValueError, match="4xx"):
        taxonomy.rate_limited(200)


# --- family(): the member behind a bare-or-parametrised code -------------------------------


def test_family_returns_the_member_for_a_bare_and_a_parametrised_code() -> None:
    """``is_reason`` answers yes/no; a policy needs to know WHICH member it matched.

    ``plan_retry`` has to distinguish ``rate-limited-429`` from ``rail-exit-137`` without
    re-implementing the hyphen-boundary rule, so the boundary lives in exactly one place.
    """
    assert taxonomy.family("receipt-empty") == "receipt-empty"
    assert taxonomy.family("rate-limited-429") == "rate-limited"
    assert taxonomy.family("timeout-1800s") == "timeout"


def test_family_returns_the_empty_string_for_a_non_member() -> None:
    assert taxonomy.family("kaboom") == ""
    assert taxonomy.family("") == ""


def test_family_honours_the_hyphen_boundary_like_is_reason() -> None:
    """The two must agree: ``rail-exiting`` is not a member, so neither answers positively."""
    assert taxonomy.family("rail-exiting") == ""
    assert taxonomy.is_reason("rail-exiting") is False
