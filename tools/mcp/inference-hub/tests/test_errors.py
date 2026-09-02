"""Tests for hub.errors: the taxonomy, HubError payloads, status classification."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hub import errors  # noqa: E402

CONTRACT_CLASSES = (
    "REGISTRY_UNAVAILABLE",
    "UNKNOWN_MODEL",
    "MODEL_DISABLED",
    "ENDPOINT_DISABLED",
    "CALLER_DENIED",
    "CREDENTIAL_MISSING",
    "REFUSED_SECRET_IN_PROMPT",
    "UNSUPPORTED_CAPABILITY",
    "INVALID_ARGUMENT",
    "BACKEND_AUTH",
    "BACKEND_RATE_LIMITED",
    "BACKEND_UNAVAILABLE",
    "BACKEND_ERROR",
    "MALFORMED_RESPONSE",
    "TIMEOUT_NO_OUTPUT",
    "TIMEOUT_PARTIAL",
    "BUDGET_EXCEEDED",
    "CONCURRENCY_SATURATED",
    "HALTED",
)


def test_taxonomy_matches_contract() -> None:
    assert errors.ERROR_CLASSES == CONTRACT_CLASSES
    assert len(set(errors.ERROR_CLASSES)) == 19
    for name in CONTRACT_CLASSES:
        assert getattr(errors, name) == name


def test_retryable_set() -> None:
    assert errors.RETRYABLE == frozenset(
        {
            errors.BACKEND_RATE_LIMITED,
            errors.BACKEND_UNAVAILABLE,
            errors.TIMEOUT_NO_OUTPUT,
            errors.CONCURRENCY_SATURATED,
        }
    )
    assert errors.RETRYABLE <= set(errors.ERROR_CLASSES)


def test_hub_error_defaults_and_payload() -> None:
    err = errors.HubError(errors.BACKEND_RATE_LIMITED, "slow down")
    assert err.klass == errors.BACKEND_RATE_LIMITED
    assert err.message == "slow down"
    assert err.retryable is True
    assert err.endpoint is None
    assert err.model is None
    assert str(err) == "BACKEND_RATE_LIMITED: slow down"
    assert err.to_payload() == {
        "error": {
            "class": "BACKEND_RATE_LIMITED",
            "message": "slow down",
            "retryable": True,
            "endpoint": None,
            "model": None,
        }
    }


def test_hub_error_explicit_fields() -> None:
    err = errors.HubError(
        errors.UNKNOWN_MODEL,
        "no such model",
        endpoint="hf-router",
        model="glm-5.3",
        retryable=True,
    )
    assert err.retryable is True
    payload = err.to_payload()["error"]
    assert payload["endpoint"] == "hf-router"
    assert payload["model"] == "glm-5.3"
    non_retryable = errors.HubError(errors.BACKEND_UNAVAILABLE, "x", retryable=False)
    assert non_retryable.retryable is False
    assert isinstance(err, Exception)


def test_hub_error_rejects_unknown_class() -> None:
    with pytest.raises(ValueError, match="unknown error class"):
        errors.HubError("NOT_A_CLASS", "boom")


def test_hub_error_sanitises_message() -> None:
    err = errors.HubError(errors.BACKEND_ERROR, "line1\nline2\x00\x1b[31m " + "z" * 500)
    assert "\n" not in err.message
    assert "\x00" not in err.message
    assert len(err.message) <= 300
    assert err.message.endswith("...")
    empty = errors.HubError(errors.HALTED)
    assert empty.message == ""


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, errors.BACKEND_AUTH),
        (403, errors.BACKEND_AUTH),
        (429, errors.BACKEND_RATE_LIMITED),
        (500, errors.BACKEND_UNAVAILABLE),
        (503, errors.BACKEND_UNAVAILABLE),
        (599, errors.BACKEND_UNAVAILABLE),
        (400, errors.BACKEND_ERROR),
        (404, errors.BACKEND_ERROR),
        (418, errors.BACKEND_ERROR),
        (302, errors.BACKEND_ERROR),
        (600, errors.BACKEND_ERROR),
    ],
)
def test_classify_http_status(status: int, expected: str) -> None:
    assert errors.classify_http_status(status) == expected


def test_safe_message_strips_controls_and_collapses_whitespace() -> None:
    raw = "  a\tb\r\nc\x07d\u200be  \x7f f "
    assert errors.safe_message(raw) == "a b c d e f"
    assert errors.safe_message("") == ""
    assert errors.safe_message(ValueError("bad value")) == "bad value"


def test_safe_message_truncates_to_limit() -> None:
    long = "word " * 100
    out = errors.safe_message(long, limit=40)
    assert len(out) <= 40
    assert out.endswith("...")
    assert errors.safe_message("abcdef", limit=6) == "abcdef"
    assert errors.safe_message("abcdefgh", limit=2) == "ab"
    assert errors.safe_message("abcdefgh", limit=3) == "..."
