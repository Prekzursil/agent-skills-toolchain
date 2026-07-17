"""Pytest bootstrap for the workflow-monitor skill.

Puts the skill root on ``sys.path`` so tests under ``tests/`` can import the flat top-level
modules ``workflow_run`` and ``wfmon_export`` without an installed package, and pins the
cockpit's Codex panel (PR-B3) to EMPTY per-test dirs so no test ever reads the machine's
real ``%TEMP%/codex-streams`` or ``~/.codex/sessions`` (hermeticity: the Pilot keybind
tests construct the real ``WorkflowMonitor``, whose poll worker also polls ``CodexSource``).
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))


@pytest.fixture(autouse=True)
def _hermetic_codex_dirs(tmp_path_factory, monkeypatch):
    """Point the Codex panel's default dirs at fresh empty paths for every test."""
    root = tmp_path_factory.mktemp("codex-hermetic")
    monkeypatch.setenv("CODEX_STREAM_DIR", str(root / "streams"))
    monkeypatch.setenv("CODEX_HOME", str(root / "codex"))
