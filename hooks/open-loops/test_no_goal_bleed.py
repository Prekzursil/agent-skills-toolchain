"""Regression: a goal written by one session must not resurface in another.

MEASURED DEFECT (2026-08-08). `ledger_open_loops()` in `_common.py` read `ledger.state(cwd)`,
which is keyed by cwd ALONE -- `ledger.py:402 state(project_path)` takes no session parameter.
So the LAST goal written in a directory was injected into every later session that started there,
as an open loop it was nudged to re-enter. This hook is WIRED at SessionStart in
`_dispatch/manifest.json`, so it fired on every fresh start.

Reproduced before the fix: session B received
"standing goal not yet marked complete: SESSION_A_PRIVATE_GOAL ..." -- 388 bytes leaked, while a
control with no goal in the ledger leaked 0.

There is a sibling test for the OTHER route (`event-ledger/test_replay_goal_isolation.py`, the
`sessionstart-replay.py` raw-event-tail). This file covers the route that was actually wired and
actually firing. Two routes, two tests -- the earlier partial fix closed one and left the other,
which is precisely how this survived.

WHY THE SECOND TEST MATTERS AS MUCH AS THE FIRST: deleting the whole function would pass the leak
test. `test_open_failures_still_resurface` is the negative control proving the fix removed the
goal branch WITHOUT gutting the legitimate cwd-shared behaviour. A guard that is silent in both
states measures nothing.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parent.parent
RESURFACE = HOOKS / "open-loops" / "resurface.py"
LEDGER_PY = HOOKS / "event-ledger" / "ledger.py"

GOAL = "SESSION_A_PRIVATE_GOAL wipe the staging database"
FAILURE = "SHARED_FAILURE_MARKER flaky auth probe"


def _seed(tmp_path, kind: str, text: str) -> tuple[Path, Path, dict]:
    """Write one ledger event as 'session A' into a throwaway, env-redirected store."""
    lroot = tmp_path / "ledger-root"
    olroot = tmp_path / "open-loops"
    olroot.mkdir(parents=True, exist_ok=True)
    project = tmp_path / "proj"
    project.mkdir()

    os.environ["EVENT_LEDGER_ROOT"] = str(lroot)
    spec = importlib.util.spec_from_file_location("_test_ledger", LEDGER_PY)
    led = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(led)
    led.ROOT = lroot
    led.append(str(project), kind, text=text)

    env = dict(os.environ)
    env["EVENT_LEDGER_ROOT"] = str(lroot)
    env["OPEN_LOOPS_DIR"] = str(olroot)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return project, olroot, env


def _run_fresh_sessionstart(project: Path, env: dict) -> str:
    """Run resurface.py as a FRESH start (source=startup) for a DIFFERENT session id."""
    p = subprocess.run(
        [sys.executable, "-B", str(RESURFACE)],
        input=json.dumps(
            {"cwd": str(project), "source": "startup", "session_id": "SESSION-B"}
        ),
        capture_output=True,
        text=True,
        env=env,
        timeout=90,
    )
    return p.stdout


def test_goal_from_another_session_does_not_resurface(tmp_path):
    project, _olroot, env = _seed(tmp_path, "goal", GOAL)
    out = _run_fresh_sessionstart(project, env)
    assert GOAL not in out, (
        "CROSS-SESSION BLEED: session A's goal reached SESSION-B's SessionStart context. "
        "ledger.state(cwd) is cwd-keyed with no session dimension; per-session re-anchoring "
        "belongs to ~/.agents/harness/ledger.py, which keys on sha(session_id)."
    )
    assert "standing goal not yet marked complete" not in out


def test_open_failures_still_resurface(tmp_path):
    """NEGATIVE CONTROL. Deleting the whole function would pass the test above.

    Durable project history IS legitimately shared by cwd and must survive the fix. If this goes
    red, the leak test above is passing for the wrong reason and proves nothing.
    """
    project, _olroot, env = _seed(tmp_path, "failure", FAILURE)
    out = _run_fresh_sessionstart(project, env)
    assert "unresolved failure" in out, (
        "The cwd-shared open_failures branch was removed along with the goal branch. The fix "
        "should be surgical: goal out, project history kept."
    )
