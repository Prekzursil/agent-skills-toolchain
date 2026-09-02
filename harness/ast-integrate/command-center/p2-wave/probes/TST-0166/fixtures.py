"""Isolated git fixtures for TST-0166. Never touches the worktree VCS."""
from __future__ import annotations

import subprocess
from pathlib import Path

from resume_sha_gate import git, head_sha


def _ok(proc: subprocess.CompletedProcess[str], what: str) -> str:
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"{what} failed rc={proc.returncode}: {err}")
    return (proc.stdout or "").strip()


def init_repo(root: Path) -> Path:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    _ok(git(root, "init", "-b", "main"), "git init")
    _ok(git(root, "config", "user.email", "tst0166@example.invalid"), "config email")
    _ok(git(root, "config", "user.name", "TST-0166"), "config name")
    (root / "alpha.txt").write_text("alpha-v1\n", encoding="utf-8")
    _ok(git(root, "add", "alpha.txt"), "add alpha")
    _ok(git(root, "commit", "-m", "c1-pin"), "commit c1")
    return root


def move_head(root: Path) -> str:
    """Commit a second revision that changes alpha.txt and adds beta.txt."""
    root = Path(root)
    (root / "alpha.txt").write_text("alpha-v2\n", encoding="utf-8")
    (root / "beta.txt").write_text("beta-new\n", encoding="utf-8")
    _ok(git(root, "add", "alpha.txt", "beta.txt"), "add moved files")
    _ok(git(root, "commit", "-m", "c2-moved-head"), "commit c2")
    return head_sha(root)


def independent_diff_name_only(repo: Path, pinned: str, head: str) -> list[str]:
    """Signal (b): invoke git diff --name-only directly, not through the gate."""
    proc = git(Path(repo), "diff", "--name-only", f"{pinned}..{head}")
    text = _ok(proc, "independent git diff --name-only")
    return [line for line in text.splitlines() if line.strip()]
