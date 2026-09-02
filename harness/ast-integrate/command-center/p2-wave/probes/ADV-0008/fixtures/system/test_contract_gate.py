"""Tests for the mini no-regression gate.

Probe 2 mutates contract_gate.py (the SYSTEM). This file is never edited by
the violation harness. test_always_green is a decorative mapping: it does not
observe secret logging, so CLAUSE-C3 stays green after that clause is violated.
test_does_not_exist is claimed by the fixture registry but is not defined here.
"""

from contract_gate import (
    accept_record,
    maybe_log,
    missing_artifact_exit,
    validate_payload,
)


def test_missing_field_rejected():
    result = validate_payload({})
    assert result["ok"] is False
    assert result["reason"] == "missing-required-field"


def test_partial_without_sentinel_rejected():
    result = validate_payload({"required_field": "present", "text": "incomplete"})
    assert result["ok"] is False
    assert result["reason"] == "partial-without-sentinel"


def test_always_green():
    assert 1 + 1 == 2


def test_missing_artifact_nonzero():
    assert missing_artifact_exit() != 0


def test_complete_payload_accepted():
    result = validate_payload(
        {"required_field": "present", "text": "body SUCCESS:gate"}
    )
    assert result["ok"] is True
    assert accept_record({"kind": "refutation-record"}) is True
    assert maybe_log("ok") == "ok"
