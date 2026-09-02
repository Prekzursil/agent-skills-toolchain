#!/usr/bin/env python3
"""Isolated git fixtures for IMP-0469. Never touches the delivery worktree."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

NEWER_FILE_COUNT = 25
ORIG_FILE_COUNT = 5


def git(repo: Path, *args: str, check: bool = True) -> str:
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = "IMP-0469 Probe"
    env["GIT_AUTHOR_EMAIL"] = "imp-0469@test.invalid"
    env["GIT_COMMITTER_NAME"] = env["GIT_AUTHOR_NAME"]
    env["GIT_COMMITTER_EMAIL"] = env["GIT_AUTHOR_EMAIL"]
    env["GIT_TERMINAL_PROMPT"] = "0"
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} rc={proc.returncode}: "
            f"{(proc.stderr or proc.stdout).strip()}"
        )
    return proc.stdout


def init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "-b", "main", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    git(path, "config", "user.email", "imp-0469@test.invalid")
    git(path, "config", "user.name", "IMP-0469 Probe")
    git(path, "config", "commit.gpgsign", "false")
    git(path, "config", "advice.detachedHead", "false")
    return path


def commit_all(repo: Path, message: str) -> str:
    git(repo, "add", "-A")
    git(repo, "commit", "-m", message)
    return git(repo, "rev-parse", "HEAD").strip()


def pin_origin_main(repo: Path, ref: str = "main") -> None:
    sha = git(repo, "rev-parse", ref).strip()
    git(repo, "update-ref", "refs/remotes/origin/main", sha)


def _seed_shared(repo: Path) -> None:
    (repo / "shared.txt").write_text("shared base\n", encoding="utf-8")
    for i in range(ORIG_FILE_COUNT):
        (repo / f"orig_{i}.txt").write_text(f"orig {i}\n", encoding="utf-8")


def build_stale(root: Path) -> Path:
    """Branch frozen while main gains many files the branch never touched."""
    repo = init_repo(root / "stale")
    _seed_shared(repo)
    commit_all(repo, "initial main")
    git(repo, "branch", "feature")
    for i in range(NEWER_FILE_COUNT):
        (repo / f"newer_{i}.txt").write_text(
            f"newer work on main {i}\n", encoding="utf-8"
        )
    commit_all(repo, "main gains newer work the feature branch never saw")
    pin_origin_main(repo, "main")
    git(repo, "checkout", "feature")
    (repo / "feature.txt").write_text("feature work\n", encoding="utf-8")
    (repo / "shared.txt").write_text("shared base\nfeature edit\n", encoding="utf-8")
    commit_all(repo, "feature commit")
    pin_origin_main(repo, "main")
    return repo


def build_fresh(root: Path) -> Path:
    """Feature branched from current main; no unauthored deletions."""
    repo = init_repo(root / "fresh")
    _seed_shared(repo)
    for i in range(NEWER_FILE_COUNT):
        (repo / f"newer_{i}.txt").write_text(
            f"already on main {i}\n", encoding="utf-8"
        )
    commit_all(repo, "current main")
    pin_origin_main(repo, "main")
    git(repo, "checkout", "-b", "feature")
    (repo / "feature.txt").write_text("feature work\n", encoding="utf-8")
    commit_all(repo, "feature commit on current main")
    return repo


def dirty_working_tree(repo: Path, n_delete: int = 4) -> list[str]:
    """Uncommitted deletions two-dot-vs-WT will see and three-dot must not."""
    deleted: list[str] = []
    for i in range(n_delete):
        path = repo / f"orig_{i}.txt"
        if path.is_file():
            path.unlink()
            deleted.append(path.name)
    extra = repo / "uncommitted-noise.txt"
    extra.write_text("working-tree noise, not a commit\n", encoding="utf-8")
    return deleted
