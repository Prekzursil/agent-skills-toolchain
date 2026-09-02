"""Synthetic git repos proving WFA-0014's three catalog tests.

Commits happen only inside TemporaryDirectory repos, never the estate worktree.
"""
from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from gitcmd import GitError, git

from engine import sweep_branch

CI = "name: ci\non: push\njobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo ci\n"
DEPLOY = (
    "name: deploy\non: workflow_dispatch\njobs:\n  d:\n    runs-on: ubuntu-latest\n"
    "    steps:\n      - run: echo deploy-squashed\n"
)
UNIQUE = (
    "name: unique-gate\non: pull_request\njobs:\n  g:\n    runs-on: ubuntu-latest\n"
    "    steps:\n      - run: echo GENUINELY-UNIQUE-BYTES-WFA-0014\n"
)
RENAMED = "name: renamed\non: push\njobs:\n  r:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo same-bytes\n"
README = "# not a workflow\n"


def _env() -> dict[str, str]:
    e = os.environ.copy()
    e["GIT_AUTHOR_NAME"] = "wfa-0014"
    e["GIT_AUTHOR_EMAIL"] = "wfa-0014@test.invalid"
    e["GIT_COMMITTER_NAME"] = "wfa-0014"
    e["GIT_COMMITTER_EMAIL"] = "wfa-0014@test.invalid"
    e["GIT_CONFIG_NOSYSTEM"] = "1"
    return e


def _write(repo: Path, rel: str, text: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _commit(repo: Path, msg: str) -> None:
    git(repo, ["add", "-A"], env=_env())
    git(repo, ["-c", "commit.gpgsign=false", "commit", "-m", msg], env=_env())


def _init(repo: Path) -> None:
    try:
        git(repo, ["init", "-b", "main"], env=_env())
    except GitError:
        git(repo, ["init"], env=_env())
        git(repo, ["checkout", "-B", "main"], env=_env())
    git(repo, ["config", "user.email", "wfa-0014@test.invalid"], env=_env())
    git(repo, ["config", "user.name", "wfa-0014"], env=_env())
    git(repo, ["config", "commit.gpgsign", "false"], env=_env())


@contextmanager
def temp_repo() -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix="wfa0014-") as td:
        repo = Path(td)
        _init(repo)
        yield repo


def build_squash_ahead(repo: Path) -> None:
    """Branch fully squash-merged: ancestry ahead, trees equal on workflow paths."""
    _write(repo, ".github/workflows/ci.yml", CI)
    _write(repo, "README.md", README)
    _commit(repo, "main baseline")
    git(repo, ["checkout", "-b", "feature/squash-merged"], env=_env())
    _write(repo, ".github/workflows/deploy.yml", DEPLOY)
    _commit(repo, "add deploy workflow")
    git(repo, ["checkout", "main"], env=_env())
    _write(repo, ".github/workflows/deploy.yml", DEPLOY)
    _commit(repo, "squash-merge deploy onto main")


def build_unique(repo: Path) -> None:
    _write(repo, ".github/workflows/ci.yml", CI)
    _commit(repo, "main baseline")
    git(repo, ["checkout", "-b", "feature/unique-gate"], env=_env())
    _write(repo, ".github/workflows/unique-gate.yml", UNIQUE)
    _commit(repo, "add unique gate")
    git(repo, ["checkout", "main"], env=_env())


def build_additions_only(repo: Path, n: int = 40) -> None:
    _write(repo, ".github/workflows/ci.yml", CI)
    _commit(repo, "main baseline")
    git(repo, ["checkout", "-b", "feature/many-additions"], env=_env())
    for i in range(n):
        _write(
            repo,
            f".github/workflows/extra-{i:02d}.yml",
            f"name: extra-{i}\non: push\njobs:\n  j:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo {i}\n",
        )
    _commit(repo, f"add {n} workflows")
    git(repo, ["checkout", "main"], env=_env())


def build_large_modifications(repo: Path, n: int = 12) -> None:
    for i in range(n):
        _write(
            repo,
            f".github/workflows/mod-{i:02d}.yml",
            f"name: mod-{i}\non: push\njobs:\n  j:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo main-{i}\n",
        )
    _commit(repo, "main many workflows")
    git(repo, ["checkout", "-b", "feature/large-conflict"], env=_env())
    for i in range(n):
        _write(
            repo,
            f".github/workflows/mod-{i:02d}.yml",
            f"name: mod-{i}\non: push\njobs:\n  j:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo branch-{i}-CHANGED\n",
        )
    _commit(repo, "modify all workflows")
    git(repo, ["checkout", "main"], env=_env())


def build_superseded_rename(repo: Path) -> None:
    _write(repo, ".github/workflows/ci.yml", CI)
    _write(repo, ".github/workflows/new-name.yml", RENAMED)
    _commit(repo, "main has new-name")
    git(repo, ["checkout", "-b", "feature/old-name"], env=_env())
    _write(repo, ".github/workflows/old-name.yml", RENAMED)
    (repo / ".github/workflows/new-name.yml").unlink()
    _commit(repo, "rename new-name -> old-name with identical bytes")
    git(repo, ["checkout", "main"], env=_env())


def control_pack() -> dict:
    """Run every catalog control in isolated temp repos."""
    out: dict = {}
    with temp_repo() as repo:
        build_squash_ahead(repo)
        row = sweep_branch(repo, "main", "feature/squash-merged")
        out["squash_ahead"] = row
    with temp_repo() as repo:
        build_unique(repo)
        row = sweep_branch(repo, "main", "feature/unique-gate")
        out["unique"] = row
    with temp_repo() as repo:
        build_additions_only(repo, 40)
        row = sweep_branch(repo, "main", "feature/many-additions")
        out["additions_only"] = row
    with temp_repo() as repo:
        build_large_modifications(repo, 12)
        row = sweep_branch(repo, "main", "feature/large-conflict")
        out["large_modifications"] = row
    with temp_repo() as repo:
        build_superseded_rename(repo)
        row = sweep_branch(repo, "main", "feature/old-name")
        out["superseded_rename"] = row
    return out
