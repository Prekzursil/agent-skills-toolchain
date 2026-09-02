"""Scratch git worktrees for TST-0100.

Creates throwaway repos under a temp directory. Does not git add/commit/
push/stash/checkout/rebase on the delivery worktree. Isolated git env so
global config is never written.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PINNED_ORIGIN = (HERE / "pinned-origin.txt").read_text(encoding="utf-8").strip().splitlines()[0]
FOREIGN_ORIGIN = "https://github.com/other-owner/foreign-worktree.git"
ALT_PINNED_ORIGIN = "https://github.com/program/ast-integrate"


def isolated_git_env(home: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_AUTHOR_NAME"] = "tst-0100"
    env["GIT_AUTHOR_EMAIL"] = "tst-0100@invalid"
    env["GIT_COMMITTER_NAME"] = "tst-0100"
    env["GIT_COMMITTER_EMAIL"] = "tst-0100@invalid"
    env["HOME"] = str(home)
    return env


def git(cwd: Path, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=20,
        env=isolated_git_env(cwd),
        check=check,
    )


def make_repo(root: Path, origin: str | None) -> Path:
    """git init + optional `git remote add origin`. No commits."""
    root.mkdir(parents=True, exist_ok=True)
    git(root, ["init", "-q"])
    if origin is not None:
        git(root, ["remote", "add", "origin", origin])
    return root
