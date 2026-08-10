"""Pytest bootstrap and shared helpers for tools/measure-guard.

Puts the package dir on ``sys.path`` so ``import suitefloor`` / ``blobread`` / ``refcheck`` resolve
from ``tests/`` with no install step (same shape as ``tools/command-center/tests/conftest.py``).

``make_git_repo`` lives here rather than being copied per module: two test files needed the same
throwaway-repo helper and a dup-guard flagged the second copy. Every test that touches git builds its
own repo under ``tmp_path``, so nothing here reads or mutates the real repository - the
"a test running with cwd=REPO silently repairs the real tree" shape this program already found once.
"""

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def make_git_repo(root: Path) -> Path:
    """Initialise an isolated git repo at ``root`` with a committer identity configured."""
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    for key, value in (("user.email", "t@t"), ("user.name", "t")):
        subprocess.run(
            ["git", "-C", str(root), "config", key, value],
            check=True,
            capture_output=True,
        )
    return root


def commit_all(root: Path, message: str = "fixture") -> None:
    """Stage and commit everything in ``root``."""
    subprocess.run(
        ["git", "-C", str(root), "add", "-A"], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(root), "commit", "-qm", message],
        check=True,
        capture_output=True,
    )
