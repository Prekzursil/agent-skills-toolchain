"""Reporting: the envelope contract holds on BOTH paths, and every reason is agentspec's."""

from __future__ import annotations

import json

import pytest
from agentspec.envelope import (
    ENVELOPE_FIELDS,
    ErrorDetail,
    Observation,
    validate_observation,
)
from agentspec.spec import ReceiptSpec
from agentspec.taxonomy import REASONS, family

from agentrail.report import (
    AGENTRAIL_REASONS,
    UnknownReason,
    argv_too_long,
    checked_envelope,
    judge_result,
    refusal,
    resolution_failure,
    transport_failure,
)

TEXT_SPEC = ReceiptSpec(fmt="text", forbidden_markers=("still in progress",))
JSON_SPEC = ReceiptSpec(fmt="json", required_fields=("status", "summary"))
ERROR_FIELDS = ("code", "root_cause", "retry_instruction", "stop_condition")


def a_transport_failure() -> object:
    return transport_failure(
        "u1",
        "spawn-failed",
        detail="d",
        next_action="n",
        retry_instruction="r",
        stop_condition="s",
    )


def test_a_good_receipt_passes_all_six_clauses() -> None:
    report = judge_result(
        "u1",
        exit_code=0,
        receipt_bytes=b"the work is done, 3 files changed",
        spec=TEXT_SPEC,
        wall_ms=120,
    )
    assert report.ok is True
    assert report.verdict is not None
    assert report.verdict.ok is True
    assert report.terminal == "SUCCESS:u1"
    assert report.observation.status == "success"


def test_exit_zero_with_a_progress_body_is_severed_not_success() -> None:
    """Blocking on process exit is NOT proof of completion."""
    report = judge_result(
        "u1",
        exit_code=0,
        receipt_bytes=b"the task is still in progress",
        spec=TEXT_SPEC,
    )
    assert report.ok is False
    assert report.verdict is not None
    assert report.verdict.severed is True
    assert report.verdict.reason == "receipt-incomplete"
    assert report.terminal == "FAILED:u1 severed-stream (receipt-incomplete)"


def test_a_non_zero_exit_is_a_rail_failure_not_a_severed_stream() -> None:
    report = judge_result("u1", exit_code=7, receipt_bytes=None, spec=TEXT_SPEC)
    assert report.verdict is not None
    assert report.verdict.severed is False
    assert report.terminal == "FAILED:u1 rail-exit-7"


def test_a_json_receipt_missing_a_required_field_fails_the_schema_clause() -> None:
    report = judge_result(
        "u1", exit_code=0, receipt_bytes=b'{"status":"ok"}', spec=JSON_SPEC
    )
    assert report.verdict is not None
    assert report.verdict.reason == "schema-invalid"


def test_the_progress_stream_is_diagnostics_and_never_the_answer() -> None:
    report = judge_result(
        "u1",
        exit_code=0,
        receipt_bytes=b"real answer",
        spec=TEXT_SPEC,
        progress="[worker] launched in the background",
    )
    assert report.ok is True


@pytest.mark.parametrize(
    "report_factory",
    [
        lambda: judge_result(
            "u1", exit_code=0, receipt_bytes=b"done properly", spec=TEXT_SPEC
        ),
        lambda: judge_result("u1", exit_code=3, receipt_bytes=None, spec=TEXT_SPEC),
        a_transport_failure,
        lambda: resolution_failure("u1", "codex", "env-missing-codex", tried=("/a",)),
        lambda: refusal("u1", ("missing-timeout",)),
        lambda: argv_too_long("u1", cmdline_len=40000, cap=32767),
    ],
)
def test_every_path_carries_all_four_envelope_fields(report_factory: object) -> None:
    """THE envelope contract: success AND failure, no exceptions."""
    report = report_factory()  # pyright: ignore[reportCallIssue]
    payload = report.as_dict()
    for field in ENVELOPE_FIELDS:
        assert field in payload, f"{field} missing from {payload}"
    assert payload["summary"]
    assert payload["next_actions"], "error-only output without next steps is banned"
    assert isinstance(payload["artifacts"], list)
    assert payload["terminal"]
    json.dumps(payload)


@pytest.mark.parametrize(
    "report_factory",
    [
        lambda: judge_result("u1", exit_code=3, receipt_bytes=None, spec=TEXT_SPEC),
        a_transport_failure,
        lambda: resolution_failure("u1", "codex", "env-missing-codex", tried=("/a",)),
        lambda: refusal("u1", ("missing-timeout",)),
        lambda: argv_too_long("u1", cmdline_len=40000, cap=32767),
    ],
)
def test_every_error_path_carries_the_full_error_detail(report_factory: object) -> None:
    report = report_factory()  # pyright: ignore[reportCallIssue]
    detail = report.as_dict()["error"]
    assert isinstance(detail, dict)
    for field in ERROR_FIELDS:
        assert detail[field], f"{field} is empty on {report.terminal}"
    assert family(str(detail["code"])) in REASONS


def test_a_reason_outside_the_closed_taxonomy_is_refused() -> None:
    with pytest.raises(UnknownReason, match="not in the closed agentspec taxonomy"):
        transport_failure(
            "u1",
            "rail-was-grumpy",
            detail="d",
            next_action="n",
            retry_instruction="r",
            stop_condition="s",
        )


def test_agentrail_reasons_are_a_subset_of_the_agentspec_taxonomy() -> None:
    assert set(AGENTRAIL_REASONS) <= set(REASONS)
    assert AGENTRAIL_REASONS == tuple(sorted(AGENTRAIL_REASONS))


def test_a_parametrised_reason_renders_its_family_in_the_terminal_marker() -> None:
    report = resolution_failure("u1", "codex", "env-missing-codex", tried=())
    assert report.terminal == "FAILED:u1 env-missing"
    assert report.as_dict()["error"] == {
        "code": "env-missing-codex",
        "root_cause": report.observation.error.root_cause,  # pyright: ignore[reportOptionalMemberAccess]
        "retry_instruction": report.observation.error.retry_instruction,  # pyright: ignore[reportOptionalMemberAccess]
        "stop_condition": report.observation.error.stop_condition,  # pyright: ignore[reportOptionalMemberAccess]
    }


def test_a_malformed_envelope_is_rejected_rather_than_shipped() -> None:
    """The shared validator, not a local opinion, decides what 'malformed' means."""
    bad = Observation(
        status="error",
        summary="broken",
        next_actions=(),
        artifacts=(),
        error=ErrorDetail(
            code="nope", root_cause="", retry_instruction="", stop_condition=""
        ),
    )
    assert validate_observation(bad) != ()
    with pytest.raises(UnknownReason, match="malformed observation envelope"):
        checked_envelope(bad)


def test_a_well_formed_envelope_passes_the_validator_unchanged() -> None:
    good = a_transport_failure().observation
    assert checked_envelope(good) is good


def test_the_report_exposes_the_verdict_only_when_a_rail_produced_one() -> None:
    judged = judge_result("u1", exit_code=0, receipt_bytes=b"done", spec=TEXT_SPEC)
    assert judged.verdict is not None
    assert a_transport_failure().verdict is None
