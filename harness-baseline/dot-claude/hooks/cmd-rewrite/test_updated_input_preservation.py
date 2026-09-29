"""Regression: `updatedInput` REPLACES tool_input, so unchanged fields must survive.

The PreToolUse decision-control contract says the replacement object is the whole
input: fields omitted from it are dropped, not merged. This hook emitted a bare
`{"command": rewritten}`, so a call sent as

    {"command": "git log --oneline", "description": "history",
     "timeout": 600000, "run_in_background": true}

came back as a foreground call at the default timeout with no description -- the
hook silently rewrote the CALLER's request, not just the command string.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
HOOK = HERE / "inject-nopager.py"


def _run(payload: dict) -> tuple[int, str]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    return proc.returncode, proc.stdout


def _updated_input(stdout: str) -> dict:
    return json.loads(stdout)["hookSpecificOutput"]["updatedInput"]


FULL_INPUT = {
    "command": "git log --oneline",
    "description": "history",
    "timeout": 600000,
    "run_in_background": True,
}


def test_rewrite_preserves_every_sibling_field():
    rc, out = _run({"tool_name": "Bash", "tool_input": dict(FULL_INPUT)})
    assert rc == 0
    updated = _updated_input(out)
    assert updated["description"] == "history"
    assert updated["timeout"] == 600000
    assert updated["run_in_background"] is True


def test_rewrite_still_changes_the_command():
    """Positive control: a fix that just echoes tool_input back fails here."""
    rc, out = _run({"tool_name": "Bash", "tool_input": dict(FULL_INPUT)})
    assert rc == 0
    assert _updated_input(out)["command"] == "git --no-pager log --oneline"


def test_updated_input_is_the_whole_input_plus_the_rewrite():
    rc, out = _run({"tool_name": "Bash", "tool_input": dict(FULL_INPUT)})
    assert rc == 0
    assert _updated_input(out) == {
        **FULL_INPUT,
        "command": "git --no-pager log --oneline",
    }


def test_unknown_future_fields_are_carried_through():
    """The hook must not need to know a field to preserve it."""
    payload = dict(FULL_INPUT)
    payload["some_future_field"] = {"nested": [1, 2]}
    rc, out = _run({"tool_name": "Bash", "tool_input": payload})
    assert rc == 0
    assert _updated_input(out)["some_future_field"] == {"nested": [1, 2]}


def test_the_hook_does_not_mutate_a_command_it_has_no_rule_for():
    """No rewrite -> no output at all, so nothing can be dropped."""
    rc, out = _run(
        {"tool_name": "Bash", "tool_input": {"command": "echo hi", "timeout": 5}}
    )
    assert (rc, out) == (0, "")


@pytest.mark.parametrize(
    "payload",
    [
        {"tool_name": "Read", "tool_input": {"command": "git log"}},
        {"tool_name": "Bash", "tool_input": {"command": "   "}},
        {"tool_name": "Bash", "tool_input": {}},
        {"tool_name": "Bash", "tool_input": "not-a-dict"},
    ],
)
def test_fail_open_paths_stay_silent(payload):
    rc, out = _run(payload)
    assert (rc, out) == (0, "")
