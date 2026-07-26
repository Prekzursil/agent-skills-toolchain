"""The COMPLETION ORACLE — the single most important function in the package.

SUCCESS requires exit code 0 AND a receipt that exists AND is non-empty AND parses AND
validates against the caller's schema AND carries no "not finished" marker. Exit 0 with no
usable receipt is SEVERED, never SUCCESS.

Every clause below gets its own test that goes RED if the clause is deleted — that pairing is
asserted mechanically in tests/test_mutations.py.
"""

from __future__ import annotations

import json

import pytest

from agentspec.envelope import validate_observation
from agentspec.oracle import CLAUSES, RailResult, judge, observe
from agentspec.spec import ReceiptSpec

JSON_SPEC = ReceiptSpec(fmt="json", required_fields=("status", "summary"))
TEXT_SPEC = ReceiptSpec(fmt="text", forbidden_markers=("in progress", "unable to"))

GOOD_JSON = json.dumps({"status": "ok", "summary": "3 files changed"}).encode()
GOOD_TEXT = b"Done: 3 files changed."


def test_clauses_are_the_declared_ordered_and_gate() -> None:
    assert CLAUSES == (
        "exit-zero",
        "receipt-present",
        "receipt-non-empty",
        "receipt-parses",
        "receipt-schema",
        "receipt-content",
    )


def test_a_fully_good_json_run_is_success_with_every_clause_passed() -> None:
    verdict = judge("u1", RailResult(exit_code=0, receipt_bytes=GOOD_JSON), JSON_SPEC)
    assert verdict.ok is True
    assert verdict.reason is None
    assert verdict.severed is False
    assert verdict.passed_clauses == CLAUSES
    assert verdict.payload == {"status": "ok", "summary": "3 files changed"}


def test_a_fully_good_text_run_is_success() -> None:
    verdict = judge("u1", RailResult(exit_code=0, receipt_bytes=GOOD_TEXT), TEXT_SPEC)
    assert verdict.ok is True
    assert verdict.text == "Done: 3 files changed."


# --- clause 1: exit code ------------------------------------------------------------------


def test_a_non_zero_exit_fails_with_the_rail_exit_reason_and_is_not_severed() -> None:
    verdict = judge("u1", RailResult(exit_code=137, receipt_bytes=GOOD_JSON), JSON_SPEC)
    assert verdict.ok is False
    assert verdict.reason == "rail-exit-137"
    assert verdict.severed is False
    assert verdict.passed_clauses == ()


def test_a_non_zero_exit_is_judged_even_when_the_receipt_is_perfect() -> None:
    """Clause 1 is independently necessary: a good receipt cannot rescue a bad exit."""
    assert (
        judge("u1", RailResult(exit_code=1, receipt_bytes=GOOD_JSON), JSON_SPEC).ok
        is False
    )


# --- clause 2..6: exit 0 with an unusable receipt is SEVERED -------------------------------


def test_exit_zero_with_a_missing_receipt_is_severed() -> None:
    verdict = judge("u1", RailResult(exit_code=0, receipt_bytes=None), JSON_SPEC)
    assert verdict.ok is False
    assert verdict.reason == "receipt-missing"
    assert verdict.severed is True
    assert verdict.passed_clauses == ("exit-zero",)


@pytest.mark.parametrize("empty", [b"", b"   ", b"\r\n\t "])
def test_exit_zero_with_an_empty_receipt_is_severed(empty: bytes) -> None:
    verdict = judge("u1", RailResult(exit_code=0, receipt_bytes=empty), JSON_SPEC)
    assert verdict.reason == "receipt-empty"
    assert verdict.severed is True
    assert verdict.passed_clauses == ("exit-zero", "receipt-present")


def test_exit_zero_with_an_unparseable_receipt_is_severed() -> None:
    verdict = judge(
        "u1", RailResult(exit_code=0, receipt_bytes=b"{not json"), JSON_SPEC
    )
    assert verdict.reason == "receipt-unparseable"
    assert verdict.severed is True


def test_exit_zero_with_invalid_utf8_is_severed_as_unparseable() -> None:
    verdict = judge("u1", RailResult(exit_code=0, receipt_bytes=b"\xff\xfe"), JSON_SPEC)
    assert verdict.reason == "receipt-unparseable"
    assert verdict.severed is True


def test_exit_zero_with_a_schema_violation_is_severed_and_names_the_field() -> None:
    verdict = judge(
        "u1", RailResult(exit_code=0, receipt_bytes=b'{"status": "ok"}'), JSON_SPEC
    )
    assert verdict.reason == "schema-invalid"
    assert verdict.severed is True
    assert "summary" in verdict.detail
    assert verdict.passed_clauses == (
        "exit-zero",
        "receipt-present",
        "receipt-non-empty",
        "receipt-parses",
    )


def test_exit_zero_over_an_in_progress_text_body_is_severed_not_success() -> None:
    """The measured sibling of F-TRUNCATE: a receipt written over a malformed body.

    Non-empty, valid text, no schema — a two-clause gate reports SUCCESS here.
    """
    body = b"I was unable to complete this; work is still in progress."
    verdict = judge("u1", RailResult(exit_code=0, receipt_bytes=body), TEXT_SPEC)
    assert verdict.ok is False
    assert verdict.reason == "receipt-incomplete"
    assert verdict.severed is True
    assert "in progress" in verdict.detail


def test_a_progress_stream_written_as_the_receipt_is_severed() -> None:
    body = b"started in the background as task-91af"
    verdict = judge("u1", RailResult(exit_code=0, receipt_bytes=body), TEXT_SPEC)
    assert verdict.ok is False
    assert verdict.reason == "progress-stream"
    assert verdict.severed is True


def test_the_progress_STREAM_field_is_never_parsed_as_the_result() -> None:
    """The receipt is the ONLY result source; `progress` is diagnostics."""
    verdict = judge(
        "u1",
        RailResult(
            exit_code=0,
            receipt_bytes=None,
            progress="[codex] done\nThe answer is 42.\n",
        ),
        JSON_SPEC,
    )
    assert verdict.ok is False
    assert verdict.reason == "receipt-missing"
    assert "42" not in (verdict.text or "")
    assert verdict.payload is None


def test_a_json_receipt_carrying_a_forbidden_marker_is_caught_too() -> None:
    spec = ReceiptSpec(
        fmt="json", required_fields=("status",), forbidden_markers=("in progress",)
    )
    body = json.dumps({"status": "work is still in progress"}).encode()
    assert judge("u1", RailResult(exit_code=0, receipt_bytes=body), spec).reason == (
        "receipt-incomplete"
    )


# --- RailResult hygiene -------------------------------------------------------------------


def test_rail_result_wall_ms_defaults_to_zero_and_is_an_int() -> None:
    result = RailResult(exit_code=0, receipt_bytes=GOOD_JSON)
    assert result.wall_ms == 0
    assert isinstance(result.wall_ms, int)


def test_rail_result_refuses_a_float_wall_ms() -> None:
    with pytest.raises(TypeError, match="int"):
        RailResult(exit_code=0, receipt_bytes=GOOD_JSON, wall_ms=1.5)  # type: ignore[arg-type]


def test_rail_result_refuses_a_negative_wall_ms() -> None:
    with pytest.raises(ValueError, match="wall_ms"):
        RailResult(exit_code=0, receipt_bytes=GOOD_JSON, wall_ms=-1)


def test_failure_reason_is_total_over_both_verdict_shapes() -> None:
    """The accessor exists so no call site needs an assert (an always-true assert is an
    uncoverable branch, i.e. a self-inflicted coverage hole)."""
    ok = judge("u1", RailResult(exit_code=0, receipt_bytes=GOOD_JSON), JSON_SPEC)
    bad = judge("u1", RailResult(exit_code=9, receipt_bytes=GOOD_JSON), JSON_SPEC)
    assert ok.failure_reason == ""
    assert bad.failure_reason == "rail-exit-9"


def test_judge_refuses_an_empty_unit_id() -> None:
    with pytest.raises(ValueError, match="unit_id"):
        judge("", RailResult(exit_code=0, receipt_bytes=GOOD_JSON), JSON_SPEC)


def test_judge_refuses_a_receipt_spec_with_an_unknown_format() -> None:
    with pytest.raises(ValueError, match="fmt"):
        judge(
            "u1",
            RailResult(exit_code=0, receipt_bytes=GOOD_JSON),
            ReceiptSpec(fmt="yaml"),
        )


# --- the envelope projection ---------------------------------------------------------------


def test_observe_projects_a_success_verdict_onto_the_envelope() -> None:
    verdict = judge("u1", RailResult(exit_code=0, receipt_bytes=GOOD_JSON), JSON_SPEC)
    obs = observe(verdict, artifacts=("out/u1.json",))
    assert obs.status == "success"
    assert obs.artifacts == ("out/u1.json",)
    assert validate_observation(obs) == ()


@pytest.mark.parametrize(
    ("exit_code", "body"),
    [
        (137, GOOD_JSON),
        (0, None),
        (0, b""),
        (0, b"{oops"),
        (0, b'{"status": "ok"}'),
    ],
)
def test_every_error_projection_carries_root_cause_retry_and_stop_condition(
    exit_code: int, body: bytes | None
) -> None:
    verdict = judge(
        "u1", RailResult(exit_code=exit_code, receipt_bytes=body), JSON_SPEC
    )
    obs = observe(verdict)
    assert obs.status == "error"
    assert obs.error is not None
    assert obs.error.root_cause.strip()
    assert obs.error.retry_instruction.strip()
    assert obs.error.stop_condition.strip()
    assert obs.next_actions
    assert validate_observation(obs) == ()


def test_a_severed_projection_names_severed_stream_in_its_root_cause() -> None:
    verdict = judge("u1", RailResult(exit_code=0, receipt_bytes=None), JSON_SPEC)
    assert "severed-stream" in observe(verdict).error.root_cause  # type: ignore[union-attr]


def test_an_incomplete_text_projection_carries_the_content_reason() -> None:
    body = b"work is still in progress"
    verdict = judge("u1", RailResult(exit_code=0, receipt_bytes=body), TEXT_SPEC)
    obs = observe(verdict)
    assert obs.error is not None
    assert obs.error.code == "receipt-incomplete"
    assert validate_observation(obs) == ()
