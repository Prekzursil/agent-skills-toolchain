"""The shared observation envelope: status / summary / next_actions / artifacts.

Error paths additionally carry a root-cause hint, a safe retry instruction and an EXPLICIT
stop condition. "error-only output without next steps" is a named anti-pattern.
"""

from __future__ import annotations

import dataclasses

import pytest

from agentspec.envelope import (
    ENVELOPE_FIELDS,
    ErrorDetail,
    Observation,
    error,
    success,
    validate_observation,
    warning,
)


def _err() -> ErrorDetail:
    return ErrorDetail(
        code="receipt-empty",
        root_cause="the rail exited 0 but wrote a zero-byte receipt",
        retry_instruction="re-dispatch the SAME unit once with --output-last-message set",
        stop_condition="stop after 1 retry; escalate as severed-stream",
    )


def test_envelope_fields_are_the_four_mandated_names() -> None:
    assert ENVELOPE_FIELDS == ("status", "summary", "next_actions", "artifacts")


def test_success_builds_a_valid_envelope() -> None:
    obs = success("unit ran", next_actions=("review the diff",), artifacts=("out/a.json",))
    assert obs.status == "success"
    assert obs.next_actions == ("review the diff",)
    assert obs.artifacts == ("out/a.json",)
    assert obs.error is None
    assert validate_observation(obs) == ()


def test_warning_builds_a_valid_envelope() -> None:
    obs = warning("unit ran but the budget is 90% spent", next_actions=("raise the cap",))
    assert obs.status == "warning"
    assert validate_observation(obs) == ()


def test_error_requires_and_carries_all_three_recovery_fields() -> None:
    obs = error("receipt was empty", _err(), next_actions=("re-dispatch once",))
    assert obs.status == "error"
    assert obs.error is not None
    assert obs.error.root_cause
    assert obs.error.retry_instruction
    assert obs.error.stop_condition
    assert validate_observation(obs) == ()


def test_observation_is_frozen() -> None:
    obs = success("ok")
    with pytest.raises(dataclasses.FrozenInstanceError):
        obs.status = "error"  # type: ignore[misc]


def test_error_detail_is_frozen() -> None:
    detail = _err()
    with pytest.raises(dataclasses.FrozenInstanceError):
        detail.code = "x"  # type: ignore[misc]


def test_as_dict_emits_exactly_the_four_fields_on_a_non_error() -> None:
    assert success("ok", artifacts=("a",)).as_dict() == {
        "status": "success",
        "summary": "ok",
        "next_actions": [],
        "artifacts": ["a"],
    }


def test_as_dict_adds_the_error_block_on_an_error() -> None:
    payload = error("boom", _err(), next_actions=("retry once",)).as_dict()
    assert set(payload) == {"status", "summary", "next_actions", "artifacts", "error"}
    assert payload["error"] == {
        "code": "receipt-empty",
        "root_cause": "the rail exited 0 but wrote a zero-byte receipt",
        "retry_instruction": "re-dispatch the SAME unit once with --output-last-message set",
        "stop_condition": "stop after 1 retry; escalate as severed-stream",
    }


# --- validation: one test per violation branch -------------------------------------------


def test_rejects_an_unknown_status() -> None:
    obs = Observation(status="ok", summary="s", next_actions=(), artifacts=())
    assert validate_observation(obs) == ("envelope-status-invalid",)


def test_rejects_an_empty_summary() -> None:
    obs = Observation(status="success", summary="   ", next_actions=(), artifacts=())
    assert validate_observation(obs) == ("envelope-summary-empty",)


def test_rejects_an_error_status_with_no_error_block() -> None:
    obs = Observation(status="error", summary="boom", next_actions=("retry",), artifacts=())
    assert validate_observation(obs) == ("envelope-error-missing",)


def test_rejects_a_non_error_status_carrying_an_error_block() -> None:
    obs = Observation(
        status="success", summary="fine", next_actions=(), artifacts=(), error=_err()
    )
    assert validate_observation(obs) == ("envelope-error-unexpected",)


def test_rejects_an_error_with_no_next_actions() -> None:
    """The named anti-pattern: error output with no next step."""
    obs = Observation(status="error", summary="boom", next_actions=(), artifacts=(), error=_err())
    assert validate_observation(obs) == ("envelope-next-actions-empty",)


@pytest.mark.parametrize(
    "field",
    ["root_cause", "retry_instruction", "stop_condition"],
)
def test_rejects_a_blank_recovery_field(field: str) -> None:
    obs = Observation(
        status="error",
        summary="boom",
        next_actions=("retry",),
        artifacts=(),
        error=dataclasses.replace(_err(), **{field: "  "}),
    )
    assert validate_observation(obs) == (f"envelope-error-{field.replace('_', '-')}-empty",)


def test_rejects_an_error_code_outside_the_closed_taxonomy() -> None:
    obs = Observation(
        status="error",
        summary="boom",
        next_actions=("retry",),
        artifacts=(),
        error=dataclasses.replace(_err(), code="kaboom"),
    )
    assert validate_observation(obs) == ("envelope-error-code-unknown",)


def test_reports_every_violation_at_once_sorted() -> None:
    obs = Observation(status="nope", summary="", next_actions=(), artifacts=())
    assert validate_observation(obs) == ("envelope-status-invalid", "envelope-summary-empty")


def test_error_builder_refuses_an_empty_next_actions_tuple() -> None:
    with pytest.raises(ValueError, match="next_actions"):
        error("boom", _err(), next_actions=())
