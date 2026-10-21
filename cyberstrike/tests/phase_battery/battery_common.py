#!/usr/bin/env python3
"""Shared bootstrap for the G-13 conformance battery (tests/phase_battery/*).

Resolves the repo root from this file's location (agent cwds reset between
calls - never rely on cwd), puts repo scripts/ on sys.path so every battery
test can `from verdict_recorder import VerdictRecorder`, and provides the
small shared helpers (git-show, bounded greps, subprocess) the tests use.

RAM discipline: helpers are scoped by design (single git-show, single file
read, bounded regex) - no recursive scans live here.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from verdict_recorder import (  # noqa: E402  (path bootstrap above)
    SUCCESS,
    FAILED,
    INTERRUPTED,
    PENDING_OWNER,
    VerdictRecorder,
    sha8,
)

# Commit ids (grill roadmap / GRILL-DECISIONS_2026-09-20.md)
BASELINE_REV = "2c0f3c6"  # Phase-1 baseline: pre-change snapshot
PHASE1_REV = "b7ab510"  # Phase-1 truth fixes (current HEAD at battery build)


def git(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    """Run git in REPO. Windows-shell rule: forward slashes inside git revs."""
    return subprocess.run(
        ["git", "-C", str(REPO), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
    )


def git_show(rev: str, path: str, timeout: int = 60) -> str:
    """`git show <rev>:<path>` content. path is repo-relative, forward slashes."""
    r = git(["show", f"{rev}:{path}"], timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"git show {rev}:{path} failed: {r.stderr[:300]}")
    return r.stdout


def read_text(p) -> str:
    return Path(p).read_text(encoding="utf-8", errors="replace")


def count(pattern: str, text: str, flags=re.I) -> int:
    """Occurrence count (not line count) of a regex in text."""
    return len(re.findall(pattern, text, flags))


def py_run(
    script: Path, args: list[str], timeout: int = 300
) -> subprocess.CompletedProcess:
    """Run a repo python helper with the same interpreter."""
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
    )


def json_from_completed(r: subprocess.CompletedProcess):
    """Parse stdout JSON of a completed helper run; None on failure."""
    try:
        return json.loads(r.stdout)
    except Exception:
        return None


__all__ = [
    "REPO",
    "SCRIPTS",
    "BASELINE_REV",
    "PHASE1_REV",
    "SUCCESS",
    "FAILED",
    "INTERRUPTED",
    "PENDING_OWNER",
    "VerdictRecorder",
    "sha8",
    "git",
    "git_show",
    "read_text",
    "count",
    "py_run",
    "json_from_completed",
]
