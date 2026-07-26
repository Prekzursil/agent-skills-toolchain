"""Regression proof: a camelCase payload must not hide the tool from the guard.

`ci/harness` is ruff-EXCLUDED and has no pytest lane in CI, so this file doubles
as a runnable proof:

    python ci/harness/tests/test_tool_envelope_casing.py

Measured 2026-07-26 against the live dispatcher with HARNESS_LIFECYCLE_GUARD=1:
`rm -rf /tmp/victim` sent as tool_name/tool_input was denied as an irreversible
operation, while the same command sent as toolName/toolInput normalized to an
EMPTY tool and was ALLOWED. The destructive-command guard reads tool.name and
tool.input, so a casing difference silently disabled it.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_CI = Path(__file__).resolve().parent.parent.parent  # .../ci
if str(_CI) not in sys.path:
    sys.path.insert(0, str(_CI))

from harness.adapters import normalize_event  # noqa: E402

CMD = "rm -rf /tmp/victim"
BASE: dict[str, Any] = {"session_id": "casing-regression", "cwd": "/tmp"}


def _norm(payload: dict[str, Any]):
    return normalize_event(payload, provider="claude", event_name="PreToolUse")


def test_snake_case_is_still_read() -> None:
    ev = _norm({**BASE, "tool_name": "Bash", "tool_input": {"command": CMD}})
    assert ev.tool.name == "Bash", ev.tool.name
    assert ev.tool.input.get("command") == CMD, ev.tool.input


def test_camel_case_reaches_the_guard() -> None:
    """The actual bug: this used to yield name='' and input={}, so the guard saw no tool."""
    ev = _norm({**BASE, "toolName": "Bash", "toolInput": {"command": CMD}})
    assert ev.tool.name == "Bash", f"camelCase tool name lost -> {ev.tool.name!r}"
    assert ev.tool.input.get("command") == CMD, f"camelCase tool input lost -> {ev.tool.input!r}"


def test_both_spellings_normalize_identically() -> None:
    snake = _norm({**BASE, "tool_name": "Bash", "tool_input": {"command": CMD}})
    camel = _norm({**BASE, "toolName": "Bash", "toolInput": {"command": CMD}})
    assert (snake.tool.name, snake.tool.input) == (camel.tool.name, camel.tool.input)


def test_snake_case_wins_when_both_are_present() -> None:
    ev = _norm({
        **BASE,
        "tool_name": "Bash", "tool_input": {"command": "echo canonical"},
        "toolName": "Write", "toolInput": {"command": "echo alias"},
    })
    assert ev.tool.name == "Bash", ev.tool.name
    assert ev.tool.input.get("command") == "echo canonical", ev.tool.input


def test_an_intentional_empty_input_is_not_swallowed_by_the_alias() -> None:
    """`is not None` must be preserved: an explicit {} is a real payload, not a miss."""
    ev = _norm({**BASE, "tool_name": "Bash", "tool_input": {}, "toolInput": {"command": CMD}})
    assert ev.tool.input == {}, f"explicit empty input fell through to the alias -> {ev.tool.input!r}"


def test_tool_id_aliases() -> None:
    assert _norm({**BASE, "tool_use_id": "a"}).tool.id == "a"
    assert _norm({**BASE, "toolUseId": "b"}).tool.id == "b"
    assert _norm({**BASE, "toolId": "c"}).tool.id == "c"


def test_missing_tool_fields_stay_empty() -> None:
    ev = _norm({**BASE})
    assert ev.tool.name == ""
    assert ev.tool.input == {}


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
            print(f"PASS  {name}")
        except AssertionError as e:  # noqa: PERF203
            failures += 1
            print(f"FAIL  {name}: {e}")
    print(f"\n{'FAILED' if failures else 'PASS'}: {failures} failure(s)")
    raise SystemExit(1 if failures else 0)
