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


@pytest.mark.parametrize(
    "bad",
    [
        "wu\x1b[31m07",  # a CSI colour sequence
        "wu\x1b]8;;http://evil.example\x07",  # an OSC-8 hyperlink
        "wu\x0007",  # a NUL byte
        "wu\x7f07",  # DEL
    ],
    ids=["csi", "osc8", "nul", "del"],
)
def test_a_unit_id_carrying_a_CONTROL_byte_is_refused(bad: str) -> None:
    """Whitespace was rejected; every OTHER control byte was not.

    A terminal marker is a line printed to a console, so an ESC/OSC-bearing id renders as an
    escape sequence — the measured statusline class where a field defeated its own sanitizer.
    Unit ids are spec-authored rather than rail-produced, so this is fail-closed hardening
    rather than a live escape-injection path (no rail-produced text reaches any renderer here);
    ``str.isprintable`` closes it at the boundary instead of relying on that staying true.
    """
    with pytest.raises(ValueError, match="unit_id"):
        success_line(bad)
    with pytest.raises(ValueError, match="unit_id"):
        failure_line(bad, "rail-exit-1")


def test_a_non_ascii_but_PRINTABLE_unit_id_is_still_accepted() -> None:
    """Anti-over-reach control: the check must reject control bytes, not non-ASCII text."""
    assert success_line("wu-café-07") == "SUCCESS:wu-café-07"


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
