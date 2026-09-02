#!/usr/bin/env python
"""Self-contained tests for goal-reinject/reinject.py. Run: python test_reinject.py

Uses temp directories for both EVENT_LEDGER_ROOT and GOAL_REINJECT_COUNTER_ROOT so
it never touches real ledgers or counters. Stdlib only.
"""

from __future__ import annotations

import importlib
import importlib.util
import io
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEDGER_DIR = HERE.parent / "event-ledger"

fails: list[str] = []


def check(name: str, cond: bool) -> None:
    print(f"  {'OK ' if cond else 'BAD'}  {name}")
    if not cond:
        fails.append(name)


def _run_reinject(
    tmp_ledger: str, tmp_counter: str, stdin_obj: dict
) -> tuple[int, str]:
    """Load reinject.py fresh and call main(), capturing stdout."""
    # Ensure env is patched before (re)loading
    os.environ["EVENT_LEDGER_ROOT"] = tmp_ledger
    os.environ["GOAL_REINJECT_COUNTER_ROOT"] = tmp_counter
    os.environ["GOAL_REINJECT_INTERVAL"] = "8"

    spec = importlib.util.spec_from_file_location("reinject", HERE / "reinject.py")
    mod = importlib.util.module_from_spec(spec)

    old_stdin, old_stdout = sys.stdin, sys.stdout
    sys.stdin = io.StringIO(json.dumps(stdin_obj))
    cap = io.StringIO()
    sys.stdout = cap
    try:
        spec.loader.exec_module(mod)
        rc = mod.main()
    except SystemExit as e:
        rc = int(e.code) if e.code is not None else 0
    finally:
        sys.stdin, sys.stdout = old_stdin, old_stdout
    return rc, cap.getvalue()


# ── pytest-collected regressions (C010) ──────────────────────────────────────
# `main()` below is a standalone runner that pytest does NOT collect, and this file
# is not named in quality.yml, so before these were added `pytest hooks/goal-reinject/`
# collected ZERO tests. These ride the broad `pytest hooks/` step (quality.yml:702).


def _seed_goal(tmp_ledger: str, proj: str, text: str) -> None:
    os.environ["EVENT_LEDGER_ROOT"] = tmp_ledger
    sys.path.insert(0, str(LEDGER_DIR))
    import ledger  # noqa: PLC0415

    importlib.reload(ledger)
    ledger.append(proj, "goal", text=text)


def _turns(tmp_ledger, tmp_counter, tool, session, proj, n):
    """Fire n PreToolUse turns for `tool`; return the list of stdout strings."""
    outs = []
    for _ in range(n):
        payload = {"tool_name": tool, "session_id": session, "cwd": proj}
        _rc, out = _run_reinject(tmp_ledger, tmp_counter, payload)
        outs.append(out.strip())
    return outs


def test_read_only_turns_reach_the_reinjection_interval():
    """AGENTS.md §2 says "Every N turns" — a read/search/MCP-only session must
    re-anchor at the interval. Before the fix `main()` returned at the
    Edit/Write/Bash gate, the counter stayed at 0, and the gap was unbounded."""
    tmp_ledger = tempfile.mkdtemp(prefix="reinject-ledger-")
    tmp_counter = tempfile.mkdtemp(prefix="reinject-counter-")
    proj = "/tmp/c010-readonly"
    _seed_goal(tmp_ledger, proj, "KEEP THE ROOT OBJECTIVE")

    outs = _turns(tmp_ledger, tmp_counter, "Read", "s-read", proj, 8)
    assert outs[:7] == [""] * 7, "turns 1-7 must stay silent"
    assert "KEEP THE ROOT OBJECTIVE" in outs[7], "turn 8 must re-anchor"


def test_mcp_tool_turns_also_count():
    """The same gap applied to every MCP/web tool name, not just Read."""
    tmp_ledger = tempfile.mkdtemp(prefix="reinject-ledger-")
    tmp_counter = tempfile.mkdtemp(prefix="reinject-counter-")
    proj = "/tmp/c010-mcp"
    _seed_goal(tmp_ledger, proj, "KEEP THE ROOT OBJECTIVE")

    outs = _turns(
        tmp_ledger, tmp_counter, "mcp__basic-memory__search_notes", "s-mcp", proj, 8
    )
    assert "KEEP THE ROOT OBJECTIVE" in outs[7]


def test_write_tools_still_count():
    """Regression guard: the original Edit/Write/Bash behaviour is preserved."""
    tmp_ledger = tempfile.mkdtemp(prefix="reinject-ledger-")
    tmp_counter = tempfile.mkdtemp(prefix="reinject-counter-")
    proj = "/tmp/c010-edit"
    _seed_goal(tmp_ledger, proj, "KEEP THE ROOT OBJECTIVE")

    outs = _turns(tmp_ledger, tmp_counter, "Edit", "s-edit", proj, 8)
    assert outs[:7] == [""] * 7
    assert "KEEP THE ROOT OBJECTIVE" in outs[7]


def test_event_without_tool_name_never_advances_the_counter():
    """A malformed / non-tool event must not consume cadence."""
    tmp_ledger = tempfile.mkdtemp(prefix="reinject-ledger-")
    tmp_counter = tempfile.mkdtemp(prefix="reinject-counter-")
    proj = "/tmp/c010-notool"
    _seed_goal(tmp_ledger, proj, "KEEP THE ROOT OBJECTIVE")

    for _ in range(9):
        _rc, out = _run_reinject(
            tmp_ledger, tmp_counter, {"session_id": "s-none", "cwd": proj}
        )
        assert out.strip() == ""


def main() -> int:
    tmp_ledger = tempfile.mkdtemp(prefix="reinject-ledger-")
    tmp_counter = tempfile.mkdtemp(prefix="reinject-counter-")

    # Seed a goal in the ledger for our fake project.
    os.environ["EVENT_LEDGER_ROOT"] = tmp_ledger
    sys.path.insert(0, str(LEDGER_DIR))
    import ledger  # noqa: PLC0415

    importlib.reload(ledger)

    proj = "/tmp/test-project"
    ledger.append(proj, "goal", text="ship the reinject hook")

    session = "test-session-abc123"
    payload = {"tool_name": "Edit", "session_id": session, "cwd": proj}

    print("== calls 1-7 do NOT inject ==")
    for i in range(1, 8):
        rc, out = _run_reinject(tmp_ledger, tmp_counter, payload)
        check(f"call {i}: exit 0", rc == 0)
        check(f"call {i}: no output", out.strip() == "")

    print("== call 8 injects the goal ==")
    rc, out = _run_reinject(tmp_ledger, tmp_counter, payload)
    check("call 8: exit 0", rc == 0)
    ok_json = False
    injected_goal = False
    try:
        parsed = json.loads(out.strip()) if out.strip() else {}
        ctx = parsed.get("hookSpecificOutput", {}).get("additionalContext", "")
        ok_json = bool(ctx)
        injected_goal = "ship the reinject hook" in ctx
    except Exception:
        pass
    check("call 8: emits valid JSON with hookSpecificOutput", ok_json)
    check("call 8: additionalContext contains the goal text", injected_goal)

    print("== calls 9-15 do NOT inject again ==")
    for i in range(9, 16):
        rc, out = _run_reinject(tmp_ledger, tmp_counter, payload)
        check(f"call {i}: exit 0", rc == 0)
        check(f"call {i}: no output", out.strip() == "")

    print("== call 16 injects again (second interval) ==")
    rc, out = _run_reinject(tmp_ledger, tmp_counter, payload)
    check("call 16: exit 0", rc == 0)
    try:
        parsed = json.loads(out.strip()) if out.strip() else {}
        ctx = parsed.get("hookSpecificOutput", {}).get("additionalContext", "")
        check("call 16: injects goal again", "ship the reinject hook" in ctx)
    except Exception:
        check("call 16: injects goal again", False)

    print("== no goal → no injection (even on interval boundary) ==")
    proj_nogoal = "/tmp/test-project-nogoal"
    payload_nogoal = {
        "tool_name": "Edit",
        "session_id": "sess-nogoal",
        "cwd": proj_nogoal,
    }
    # Advance counter to 8 without seeding a goal
    for _ in range(8):
        rc, out = _run_reinject(tmp_ledger, tmp_counter, payload_nogoal)
        check("no-goal call: exit 0", rc == 0)
        check("no-goal call: no output", out.strip() == "")

    print("== read-only tools DO advance the cadence (C010) ==")
    # Fresh session: 7 Read turns stay silent, the 8th Read re-anchors. Before the
    # C010 fix every one of these returned early and the counter never moved.
    sess_read = "sess-readonly"
    payload_read = {"tool_name": "Read", "session_id": sess_read, "cwd": proj}
    for i in range(1, 8):
        rc, out = _run_reinject(tmp_ledger, tmp_counter, payload_read)
        check(f"Read turn {i}: exit 0", rc == 0)
        check(f"Read turn {i}: no output", out.strip() == "")
    rc, out = _run_reinject(tmp_ledger, tmp_counter, payload_read)
    check("Read turn 8: exit 0", rc == 0)
    check("Read turn 8: injects the goal", "ship the reinject hook" in out)

    print("== an event with no tool_name does NOT advance the cadence ==")
    payload_notool = {"session_id": "sess-notool", "cwd": proj}
    for _ in range(9):
        rc, out = _run_reinject(tmp_ledger, tmp_counter, payload_notool)
        check("no tool_name: exit 0", rc == 0)
        check("no tool_name: no output", out.strip() == "")

    print("== fail-open: bad stdin → exit 0, no crash ==")
    old_stdin = sys.stdin
    sys.stdin = io.StringIO("not-json{{{{")
    cap = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = cap
    try:
        spec = importlib.util.spec_from_file_location("reinject2", HERE / "reinject.py")
        mod2 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod2)
        rc_bad = mod2.main()
    except SystemExit as e:
        rc_bad = int(e.code) if e.code is not None else 0
    finally:
        sys.stdin, sys.stdout = old_stdin, old_stdout
    check("bad stdin: exit 0 (fail-open)", rc_bad == 0)

    print(
        f"\nRESULT: {'PASS' if not fails else 'FAIL: ' + str(fails)}  "
        f"({len(fails)} failures out of {len(fails) + sum(1 for _ in range(len(fails), len(fails)))} checks)"
    )
    print("Total checks run: see above")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
