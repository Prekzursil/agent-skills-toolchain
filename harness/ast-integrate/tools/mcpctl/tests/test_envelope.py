"""Tests for the shared observation envelope.

Contract (identical across every lane of this program): status / summary /
next_actions / artifacts, and an ERROR envelope additionally carries a root-cause
hint, a safe retry instruction, and an EXPLICIT stop condition. "Error-only output
without next steps" is a named anti-pattern, so the constructor refuses it.
"""

from __future__ import annotations

import pytest

from mcpctl import envelope


def test_success_envelope_carries_the_four_mandatory_fields():
    env = envelope.success(
        "read 3 servers", next_actions=("review",), artifacts=("x.json",)
    )
    payload = env.to_dict()
    assert payload["status"] == "success"
    assert payload["summary"] == "read 3 servers"
    assert payload["next_actions"] == ["review"]
    assert payload["artifacts"] == ["x.json"]
    # A success envelope omits the error-only triple entirely rather than shipping blanks.
    assert "root_cause" not in payload


def test_warning_envelope_uses_the_warning_status():
    assert envelope.warning("partial read").status == "warning"


@pytest.mark.parametrize("status", ["success", "warning", "error"])
def test_status_is_restricted_to_the_three_contract_values(status):
    assert envelope.Envelope(status=status, summary="s").status == status


def test_an_out_of_contract_status_is_rejected():
    with pytest.raises(ValueError, match="status must be one of"):
        envelope.Envelope(status="ok", summary="s")


def test_error_envelope_carries_root_cause_retry_and_stop_condition():
    env = envelope.error(
        "could not read ~/.claude.json",
        root_cause="the file is not valid JSON",
        retry="re-run after `python -m json.tool ~/.claude.json` reports the offset",
        stop_condition="stop after one retry; a second parse failure is a corrupt file, "
        "not a transient read",
    )
    payload = env.to_dict()
    assert payload["status"] == "error"
    assert payload["root_cause"] == "the file is not valid JSON"
    assert "json.tool" in str(payload["retry"])
    assert "stop after one retry" in str(payload["stop_condition"])
    assert payload["next_actions"]


@pytest.mark.parametrize(
    ("root_cause", "retry", "stop_condition"),
    [
        ("", "r", "s"),
        ("c", "", "s"),
        ("c", "r", ""),
        ("   ", "r", "s"),
    ],
)
def test_error_envelope_refuses_a_blank_recovery_field(
    root_cause, retry, stop_condition
):
    with pytest.raises(ValueError, match="error envelope requires"):
        envelope.error(
            "boom", root_cause=root_cause, retry=retry, stop_condition=stop_condition
        )


def test_error_envelope_defaults_next_actions_to_the_retry_instruction():
    env = envelope.error("boom", root_cause="c", retry="do r", stop_condition="s")
    assert env.next_actions == ("do r",)


def test_error_envelope_keeps_explicit_next_actions():
    env = envelope.error(
        "boom", root_cause="c", retry="r", stop_condition="s", next_actions=("a", "b")
    )
    assert env.next_actions == ("a", "b")


def test_summary_and_recovery_text_are_control_stripped():
    env = envelope.error(
        "b\x1b]0;pwn\x07oom", root_cause="c\x07", retry="r\x1b", stop_condition="s\x00"
    )
    assert env.summary == "b]0;pwnoom"
    assert env.root_cause == "c"
    assert env.retry == "r"
    assert env.stop_condition == "s"


def test_terminal_line_success_and_failure_shapes():
    ok = envelope.success("all good")
    assert (
        envelope.terminal_line("mcpctl-matrix", ok) == "SUCCESS:mcpctl-matrix all good"
    )
    bad = envelope.error("blew up", root_cause="c", retry="r", stop_condition="s")
    assert (
        envelope.terminal_line("mcpctl-matrix", bad) == "FAILED:mcpctl-matrix blew up"
    )


def test_terminal_line_treats_warning_as_success_with_the_warning_visible():
    warn = envelope.warning("2 of 5 sources unreadable")
    line = envelope.terminal_line("mcpctl-matrix", warn)
    assert line.startswith("SUCCESS:mcpctl-matrix")
    assert "2 of 5 sources unreadable" in line
