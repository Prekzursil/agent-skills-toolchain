"""Every unit result renders as SUCCESS:<id> or FAILED:<id> <reason> — never prose."""

from __future__ import annotations

import json
import re

import pytest

from agentspec.oracle import RailResult, judge
from agentspec.spec import ReceiptSpec
from agentspec.terminal import TERMINAL_RE, failure_line, success_line, terminal_line

JSON_SPEC = ReceiptSpec(fmt="json", required_fields=("status",))
GOOD = json.dumps({"status": "ok"}).encode()


def test_success_line_shape() -> None:
    assert success_line("wu-07") == "SUCCESS:wu-07"


def test_failure_line_shape() -> None:
    assert failure_line("wu-07", "rail-exit-137") == "FAILED:wu-07 rail-exit-137"


def test_terminal_line_for_a_success_verdict() -> None:
    verdict = judge("wu-07", RailResult(exit_code=0, receipt_bytes=GOOD), JSON_SPEC)
    assert terminal_line(verdict) == "SUCCESS:wu-07"


def test_terminal_line_for_a_plain_failure() -> None:
    verdict = judge("wu-07", RailResult(exit_code=2, receipt_bytes=GOOD), JSON_SPEC)
    assert terminal_line(verdict) == "FAILED:wu-07 rail-exit-2"


def test_a_severed_verdict_leads_with_severed_stream_and_keeps_the_fine_cause() -> None:
    """Consumers match on `severed-stream`; the operator still needs the fine cause."""
    verdict = judge("wu-07", RailResult(exit_code=0, receipt_bytes=None), JSON_SPEC)
    assert terminal_line(verdict) == "FAILED:wu-07 severed-stream (receipt-missing)"


def test_every_terminal_line_matches_the_declared_regex() -> None:
    lines = [
        success_line("u1"),
        failure_line("u1", "timeout-1800s"),
        terminal_line(
            judge("u1", RailResult(exit_code=0, receipt_bytes=b""), JSON_SPEC)
        ),
    ]
    for line in lines:
        assert TERMINAL_RE.match(line), line


def test_the_regex_rejects_open_ended_prose() -> None:
    """Detector control: the matcher must FAIL on the thing it exists to exclude."""
    assert TERMINAL_RE.match("I finished the work, everything looks good") is None


@pytest.mark.parametrize("bad", ["", "  ", "wu 07", "wu\t07", "wu\n07"])
def test_a_unit_id_containing_whitespace_is_refused(bad: str) -> None:
    with pytest.raises(ValueError, match="unit_id"):
        success_line(bad)


def test_failure_line_refuses_a_whitespace_unit_id() -> None:
    with pytest.raises(ValueError, match="unit_id"):
        failure_line("wu 07", "rail-exit-1")


def test_failure_line_refuses_a_reason_outside_the_closed_taxonomy() -> None:
    with pytest.raises(ValueError, match="taxonomy"):
        failure_line("wu-07", "it broke somehow")


def test_failure_line_refuses_an_empty_reason() -> None:
    with pytest.raises(ValueError, match="taxonomy"):
        failure_line("wu-07", "")


def test_the_regex_is_anchored_at_both_ends() -> None:
    assert TERMINAL_RE.pattern.startswith("^")
    assert TERMINAL_RE.pattern.endswith("$")
    assert isinstance(TERMINAL_RE, re.Pattern)
