#!/usr/bin/env python3
"""Isolated git fixture for CNF-0029. Never touches the host worktree index."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from change_surface import checkout, git, measure_branch, measure_worktree_two_dot

INTEGRATION = "main"
STALE = "feature/stale"
FRESH = "feature/fresh"
AUTHOR_DESCRIPTION = (
    "Update author-intent.txt, add feature-new.txt, and delete obsolete.txt. "
    "Do not touch files the integration branch added after this branch forked."
)
INTENDED_PATHS = ["author-intent.txt", "feature-new.txt", "obsolete.txt"]
POST_FORK_COUNT = 16
NOISE_PATH = "keep.txt"
NOISE_BODY = "keep v1\nUNCOMMITTED working-tree noise folded into two-dot\n"
HISTORICAL_FILES = 1188
HISTORICAL_DELETIONS = 316222


def _date(stamp: str) -> dict[str, str]:
    return {
        "GIT_AUTHOR_DATE": stamp,
        "GIT_COMMITTER_DATE": stamp,
    }


def _write(root: Path, rel: str, body: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _commit(root: Path, message: str, stamp: str) -> str:
    git(root, "add", "-A")
    git(
        root,
        "-c",
        "user.name=CNF-0029",
        "-c",
        "user.email=cnf-0029@invalid.example",
        "commit",
        "-q",
        "-m",
        message,
        extra_env=_date(stamp),
    )
    return git(root, "rev-parse", "HEAD").strip()


def post_fork_rel(i: int) -> str:
    return f"post-fork/gained-{i:02d}.txt"


def post_fork_body(i: int) -> str:
    return "".join(f"gained after merge-base line {i:02d}.{n}\n" for n in range(8))


def build_fixture(root: Path) -> dict[str, Any]:
    """Create integration + stale + fresh branches under root (must be empty)."""
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-q", "-b", INTEGRATION)

    _write(root, "README.md", "fixture integration tree\n")
    _write(root, "author-intent.txt", "intent v1\n")
    _write(root, "keep.txt", "keep v1\n")
    _write(root, "obsolete.txt", "".join(f"obsolete line {n}\n" for n in range(5)))
    fork_sha = _commit(root, "initial integration snapshot", "2026-01-01T00:00:00 +0000")

    git(root, "branch", STALE)

    checkout(root, STALE)
    _write(root, "author-intent.txt", "intent v1\nplus feature work the author described\n")
    _write(root, "feature-new.txt", "new file authored on the feature branch\n")
    (root / "obsolete.txt").unlink()
    stale_sha = _commit(root, "author-described feature change", "2026-01-02T00:00:00 +0000")

    checkout(root, INTEGRATION)
    for i in range(POST_FORK_COUNT):
        _write(root, post_fork_rel(i), post_fork_body(i))
    integ_sha = _commit(
        root,
        "integration gained files after the stale fork",
        "2026-01-03T00:00:00 +0000",
    )
    git(root, "branch", FRESH)

    post_fork = [post_fork_rel(i) for i in range(POST_FORK_COUNT)]
    return {
        "repo": str(root),
        "integration": INTEGRATION,
        "stale": STALE,
        "fresh": FRESH,
        "fork_sha": fork_sha,
        "stale_sha": stale_sha,
        "integration_sha": integ_sha,
        "intended_paths": list(INTENDED_PATHS),
        "author_description": AUTHOR_DESCRIPTION,
        "post_fork_paths": post_fork,
        "post_fork_count": POST_FORK_COUNT,
        "historical_incident": {
            "files": HISTORICAL_FILES,
            "deletions": HISTORICAL_DELETIONS,
            "note": (
                "A leftover feature branch measured 1188 files / 316222 deletions "
                "against main when the two-dot tree compare was misread as the "
                "proposal surface. This fixture reproduces that class at "
                f"{POST_FORK_COUNT} post-fork files."
            ),
        },
    }


def apply_worktree_noise(root: Path) -> None:
    checkout(root, STALE)
    _write(root, NOISE_PATH, NOISE_BODY)


def run_audit(root: Path, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    meta = meta or {}
    intended = list(meta.get("intended_paths") or INTENDED_PATHS)
    stale = measure_branch(root, INTEGRATION, STALE, intended_paths=intended)
    fresh = measure_branch(root, INTEGRATION, FRESH, intended_paths=[])
    apply_worktree_noise(root)
    wt = measure_worktree_two_dot(root, INTEGRATION)
    stale["two_dot_worktree"] = wt
    two_commit_paths = set(
        stale["two_dot"]["added"] + stale["two_dot"]["removed"] + stale["two_dot"]["changed"]
    )
    wt_paths = set(wt["added"] + wt["removed"] + wt["changed"])
    extra = sorted(wt_paths - two_commit_paths)
    stale["worktree_noise_paths"] = extra
    stale["two_dot_hides_working_tree"] = NOISE_PATH in extra or NOISE_PATH in wt_paths
    checkout(root, INTEGRATION)
    return {
        "meta": meta,
        "stale": stale,
        "fresh": fresh,
        "control_empty": bool(fresh["three_dot"]["empty"] and fresh["two_dot"]["empty"]),
        "author_description": AUTHOR_DESCRIPTION,
        "intended_paths": intended,
    }


def run_scenario(root: Path | None = None) -> dict[str, Any]:
    owned = root is None
    if owned:
        tmp = tempfile.mkdtemp(prefix="cnf0029-")
        root = Path(tmp)
    try:
        meta = build_fixture(root)
        return run_audit(root, meta)
    finally:
        if owned:
            shutil.rmtree(root, ignore_errors=True)
