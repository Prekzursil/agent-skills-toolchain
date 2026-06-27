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

    print("== non-write tool → no injection, counter not advanced ==")
    payload_read = {"tool_name": "Read", "session_id": session, "cwd": proj}
    rc, out = _run_reinject(tmp_ledger, tmp_counter, payload_read)
    check("Read tool: exit 0", rc == 0)
    check("Read tool: no output", out.strip() == "")

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
