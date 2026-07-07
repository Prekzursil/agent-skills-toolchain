#!/usr/bin/env python3
"""pytest tests for test-tamper-guard/guard.py (PreToolUse EvilGenie diff-guard).

Run:
    pytest hooks/test-tamper-guard/test_tamper_guard.py -v
    python -m pytest hooks/test-tamper-guard/test_tamper_guard.py -v

External-anchored: every test builds a REAL throwaway git repo, stages a change,
and feeds the hook the `git commit` PreToolUse payload — the guard's verdict comes
from `git diff --cached`, exactly as in production.

Covers:
  - Each weakening signal (file_deleted / assertion_net_drop / skip_added /
    trivial_assert_added) fires under WARN (exit 0 + additionalContext).
  - G2 TEST_TAMPER_MODE=block: the three high-confidence signals exit 2 (block the
    commit); trivial_assert_added stays WARN (exit 0) even in block mode.
  - Benign diffs (non-test file, added real assertions) stay silent in BOTH modes.
  - DEFAULTS UNCHANGED: with NO TEST_TAMPER_MODE set, even a high-confidence signal
    only warns (exit 0), never blocks.
  - Fail-open (garbage stdin, non-commit command) → exit 0, no output.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = str(Path(__file__).resolve().parent / "guard.py")

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not available")

_BASELINE = "def test_add():\n    assert 1 + 1 == 2\n    assert 2 + 2 == 4\n"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    base = [
        "git",
        "-c",
        "user.email=t@example.com",
        "-c",
        "user.name=test",
        "-c",
        "commit.gpgsign=false",
        "-C",
        str(repo),
    ]
    return subprocess.run(base + list(args), capture_output=True, text=True, timeout=30)


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "test_math.py").write_text(_BASELINE, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "baseline")
    return repo


def _run_guard(
    repo: Path, mode: str | None = None, command: str = "git commit -m x"
) -> tuple[int, str, str]:
    env = dict(os.environ)
    env.pop("TEST_TAMPER_MODE", None)
    if mode is not None:
        env["TEST_TAMPER_MODE"] = mode
    payload = json.dumps({"tool_input": {"command": command}, "cwd": str(repo)})
    p = subprocess.run(
        [sys.executable, HOOK],
        input=payload,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def _fired(out: str) -> bool:
    if not out:
        return False
    try:
        return "additionalContext" in json.loads(out).get("hookSpecificOutput", {})
    except Exception:
        return False


# --- staging scenarios ------------------------------------------------------


def _stage_delete_test(repo: Path) -> None:
    _git(repo, "rm", "-q", "test_math.py")


def _stage_assertion_drop(repo: Path) -> None:
    (repo / "test_math.py").write_text(
        "def test_add():\n    assert 1 + 1 == 2\n", encoding="utf-8"
    )
    _git(repo, "add", "test_math.py")


def _stage_skip_added(repo: Path) -> None:
    (repo / "test_math.py").write_text(
        "import pytest\n\n\n@pytest.mark.skip\ndef test_add():\n"
        "    assert 1 + 1 == 2\n    assert 2 + 2 == 4\n",
        encoding="utf-8",
    )
    _git(repo, "add", "test_math.py")


def _stage_trivial_assert(repo: Path) -> None:
    (repo / "test_math.py").write_text(
        "def test_add():\n    assert 1 + 1 == 2\n    assert 2 + 2 == 4\n"
        "    assert True\n",
        encoding="utf-8",
    )
    _git(repo, "add", "test_math.py")


def _stage_real_assert_added(repo: Path) -> None:
    (repo / "test_math.py").write_text(
        "def test_add():\n    assert 1 + 1 == 2\n    assert 2 + 2 == 4\n"
        "    assert 3 + 3 == 6\n",
        encoding="utf-8",
    )
    _git(repo, "add", "test_math.py")


def _stage_non_test_change(repo: Path) -> None:
    (repo / "app.py").write_text("x = 1\n", encoding="utf-8")
    _git(repo, "add", "app.py")


# ---------------------------------------------------------------------------
# WARN mode (default) — every signal fires, exit 0
# ---------------------------------------------------------------------------


class TestWarnMode:
    def test_file_deleted_warns(self, tmp_path):
        repo = _init_repo(tmp_path)
        _stage_delete_test(repo)
        rc, out, _ = _run_guard(repo)
        assert rc == 0
        assert _fired(out)
        assert (
            "file deleted"
            in json.loads(out)["hookSpecificOutput"]["additionalContext"]
            .replace("_", " ")
            .lower()
        )

    def test_assertion_net_drop_warns(self, tmp_path):
        repo = _init_repo(tmp_path)
        _stage_assertion_drop(repo)
        rc, out, _ = _run_guard(repo)
        assert rc == 0
        assert _fired(out)

    def test_skip_added_warns(self, tmp_path):
        repo = _init_repo(tmp_path)
        _stage_skip_added(repo)
        rc, out, _ = _run_guard(repo)
        assert rc == 0
        assert _fired(out)

    def test_trivial_assert_added_warns(self, tmp_path):
        repo = _init_repo(tmp_path)
        _stage_trivial_assert(repo)
        rc, out, _ = _run_guard(repo)
        assert rc == 0
        assert _fired(out)


# ---------------------------------------------------------------------------
# G2: TEST_TAMPER_MODE=block — high-confidence signals block; trivial stays warn
# ---------------------------------------------------------------------------


class TestBlockMode:
    def test_file_deleted_blocks(self, tmp_path):
        repo = _init_repo(tmp_path)
        _stage_delete_test(repo)
        rc, _, err = _run_guard(repo, mode="block")
        assert rc == 2
        assert "block" in err.lower()

    def test_assertion_net_drop_blocks(self, tmp_path):
        repo = _init_repo(tmp_path)
        _stage_assertion_drop(repo)
        rc, _, err = _run_guard(repo, mode="block")
        assert rc == 2
        assert "block" in err.lower()

    def test_skip_added_blocks(self, tmp_path):
        repo = _init_repo(tmp_path)
        _stage_skip_added(repo)
        rc, _, err = _run_guard(repo, mode="block")
        assert rc == 2
        assert "block" in err.lower()

    def test_trivial_assert_added_stays_warn_in_block_mode(self, tmp_path):
        """trivial_assert_added has higher FP risk → warn even under block mode."""
        repo = _init_repo(tmp_path)
        _stage_trivial_assert(repo)
        rc, out, err = _run_guard(repo, mode="block")
        assert rc == 0  # NOT blocked
        assert _fired(out)

    def test_benign_silent_in_block_mode(self, tmp_path):
        repo = _init_repo(tmp_path)
        _stage_non_test_change(repo)
        rc, out, _ = _run_guard(repo, mode="block")
        assert rc == 0
        assert not _fired(out)


# ---------------------------------------------------------------------------
# Benign diffs — silent in both modes
# ---------------------------------------------------------------------------


class TestBenign:
    def test_non_test_file_silent(self, tmp_path):
        repo = _init_repo(tmp_path)
        _stage_non_test_change(repo)
        rc, out, _ = _run_guard(repo)
        assert rc == 0
        assert not _fired(out)

    def test_added_real_assertion_silent(self, tmp_path):
        repo = _init_repo(tmp_path)
        _stage_real_assert_added(repo)
        rc, out, _ = _run_guard(repo)
        assert rc == 0
        assert not _fired(out)


# ---------------------------------------------------------------------------
# DEFAULTS UNCHANGED — no env → warn only, never block
# ---------------------------------------------------------------------------


class TestDefaultsUnchanged:
    def test_default_file_deleted_warns_never_blocks(self, tmp_path):
        repo = _init_repo(tmp_path)
        _stage_delete_test(repo)
        rc, out, _ = _run_guard(repo, mode=None)
        assert rc == 0  # default never blocks
        assert _fired(out)

    def test_explicit_warn_matches_default(self, tmp_path):
        repo = _init_repo(tmp_path)
        _stage_skip_added(repo)
        rc, out, _ = _run_guard(repo, mode="warn")
        assert rc == 0
        assert _fired(out)


# ---------------------------------------------------------------------------
# Fail-open
# ---------------------------------------------------------------------------


class TestFailOpen:
    def test_garbage_stdin_exit_0(self):
        p = subprocess.run(
            [sys.executable, HOOK],
            input="not json {{{",
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert p.returncode == 0
        assert p.stdout.strip() == ""

    def test_empty_stdin_exit_0(self):
        p = subprocess.run(
            [sys.executable, HOOK],
            input="",
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert p.returncode == 0

    def test_non_commit_command_silent(self, tmp_path):
        repo = _init_repo(tmp_path)
        _stage_delete_test(repo)
        rc, out, _ = _run_guard(repo, mode="block", command="git status")
        assert rc == 0
        assert out == ""

    def test_non_git_repo_silent(self, tmp_path):
        d = tmp_path / "plain"
        d.mkdir()
        env = dict(os.environ)
        env["TEST_TAMPER_MODE"] = "block"
        payload = json.dumps(
            {"tool_input": {"command": "git commit -m x"}, "cwd": str(d)}
        )
        p = subprocess.run(
            [sys.executable, HOOK],
            input=payload,
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
        )
        assert p.returncode == 0
