"""Regression: SessionStart replay must not carry ONE session's goal into another.

`ledger.append(cwd, "goal", ...)` writes the goal TWICE -- as a raw `kind: "goal"`
event in `events.jsonl` AND as the `state.goal` singleton projection. A first fix
stopped rendering the projection, but `build_context` still selected raw `"goal"`
events into its "Recent decisions/notes" tail, so a session-B resume still
received session A's private objective -- under a heading that labels the replay
"ground truth".

Both routes must stay closed. Shared project history (decision / failure /
milestone) must still be replayed, so an inverted or over-broad fix fails too.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPLAY_HOOK = HERE / "sessionstart-replay.py"

GOAL_TEXT = "SESSION_A_ONLY rollback the production schema"
DECISION_TEXT = "SHARED_DECISION use postgres"
FAILURE_TEXT = "SHARED_FAILURE the retry loop starves the pool"
MILESTONE_TEXT = "SHARED_MILESTONE cutover completed"


def _load_ledger():
    spec = importlib.util.spec_from_file_location(
        "_test_event_ledger", HERE / "ledger.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def seeded_project(tmp_path, monkeypatch):
    """A project whose ledger holds a goal plus shared durable history."""
    root = tmp_path / "ledger-root"
    monkeypatch.setenv("EVENT_LEDGER_ROOT", str(root))
    ledger = _load_ledger()
    ledger.ROOT = root  # module read the env at import time in other test orders

    project = tmp_path / "proj"
    project.mkdir()
    proj = str(project)

    ledger.append(proj, "goal", text=GOAL_TEXT)
    ledger.append(proj, "decision", text=DECISION_TEXT)
    ledger.append(proj, "failure", text=FAILURE_TEXT)
    ledger.append(proj, "milestone", text=MILESTONE_TEXT)
    return proj, root


def _run_replay(project: str, ledger_root: Path, source: str = "resume") -> str:
    env = dict(os.environ)
    env["EVENT_LEDGER_ROOT"] = str(ledger_root)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", str(REPLAY_HOOK)],
        input=json.dumps({"cwd": project, "source": source, "session_id": "SESSION-B"}),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def _context(stdout: str) -> str:
    if not stdout.strip():
        return ""
    payload = json.loads(stdout.strip().splitlines()[-1])
    return payload["hookSpecificOutput"]["additionalContext"]


def test_peer_session_goal_is_not_replayed(seeded_project):
    """The failing case: session A's goal reaching session B's context."""
    project, root = seeded_project
    ctx = _context(_run_replay(project, root))
    assert GOAL_TEXT not in ctx
    assert "[goal]" not in ctx


def test_shared_durable_history_is_still_replayed(seeded_project):
    """Positive control -- an over-broad fix that drops the tail must fail here."""
    project, root = seeded_project
    ctx = _context(_run_replay(project, root))
    assert DECISION_TEXT in ctx
    assert MILESTONE_TEXT in ctx
    assert FAILURE_TEXT in ctx


def test_build_context_excludes_goal_kind_directly(seeded_project, monkeypatch):
    """Same assertion one layer down, so a hook-plumbing change cannot mask it."""
    project, root = seeded_project
    monkeypatch.setenv("EVENT_LEDGER_ROOT", str(root))
    spec = importlib.util.spec_from_file_location("_test_replay_mod", REPLAY_HOOK)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    mod.ledger.ROOT = root

    ctx = mod.build_context(project)
    assert ctx is not None
    assert GOAL_TEXT not in ctx
    assert DECISION_TEXT in ctx
