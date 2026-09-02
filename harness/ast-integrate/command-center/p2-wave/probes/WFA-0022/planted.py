#!/usr/bin/env python3
"""Planted git+live fixture for WFA-0022 both-states controls.

Four planted artifacts:
  keep.yml          still on HEAD (control: recovery must not invent deletion)
  abandoned.yml     committed, then deleted; blob remains in git objects
  salvage copy      live-tree byte-identical copy of abandoned.yml
  lost-unique.yml   never stored in git or live (both surfaces miss -> LOST)
  CHANGELOG mention of a path whose bytes are absent (must not count as preserved)
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from engine import lf, sha256_lf

KEEP_BODY = b"WFA-0022 planted keep workflow still on HEAD\n"
ABANDONED_BODY = b"WFA-0022 planted abandoned orchestrator UNIQUE-BYTES-ABANDONED\n"
LOST_BODY = b"WFA-0022 planted lost-unique workflow NEVER-STORED-BYTES\n"
KEEP_PATH = "workflows/keep.yml"
ABANDONED_PATH = "workflows/abandoned-orchestrator.yml"
LOST_PATH = "workflows/lost-unique.yml"
SALVAGE_REL = "salvage/abandoned-orchestrator.yml"
CHANGELOG = "CHANGELOG.md"
NEVER_COMMITTED = "workflows/never-committed.yml"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_AUTHOR_NAME": "WFA-0022",
            "GIT_AUTHOR_EMAIL": "wfa-0022@test.invalid",
            "GIT_COMMITTER_NAME": "WFA-0022",
            "GIT_COMMITTER_EMAIL": "wfa-0022@test.invalid",
            "GIT_AUTHOR_DATE": "2026-08-01T00:00:00Z",
            "GIT_COMMITTER_DATE": "2026-08-01T00:00:00Z",
        }
    )
    p = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if p.returncode != 0:
        raise RuntimeError(
            f"fixture git {args} rc={p.returncode}: {(p.stderr or p.stdout or '').strip()}"
        )
    return p


def write_bytes(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def build(root: Path) -> dict:
    """Create git repo + live tree under root. Returns descriptor with hashes."""
    git_repo = root / "git-repo"
    live = root / "live-tree"
    git_repo.mkdir(parents=True, exist_ok=True)
    live.mkdir(parents=True, exist_ok=True)

    _git(git_repo, "init", "-b", "main")
    _git(git_repo, "config", "user.email", "wfa-0022@test.invalid")
    _git(git_repo, "config", "user.name", "WFA-0022")

    write_bytes(git_repo / KEEP_PATH, KEEP_BODY)
    write_bytes(git_repo / ABANDONED_PATH, ABANDONED_BODY)
    _git(git_repo, "add", KEEP_PATH, ABANDONED_PATH)
    _git(git_repo, "commit", "-m", "WFA-0022 plant keep+abandoned")

    _git(git_repo, "rm", ABANDONED_PATH)
    _git(git_repo, "commit", "-m", "WFA-0022 DELETE abandoned orchestrator")

    write_bytes(live / SALVAGE_REL, ABANDONED_BODY)
    write_bytes(
        live / CHANGELOG,
        (
            "Deleted workflows/lost-unique.yml in the DELETE-ALL retirement.\n"
            "Also retired workflows/abandoned-orchestrator.yml; salvage lives elsewhere.\n"
        ).encode("utf-8"),
    )
    # Mention-only: path named, bytes of LOST_BODY never written anywhere.

    keep_sha = sha256_lf(KEEP_BODY)
    abandoned_sha = sha256_lf(ABANDONED_BODY)
    lost_sha = sha256_lf(LOST_BODY)
    head = _git(git_repo, "rev-parse", "HEAD").stdout.strip()
    return {
        "git_repo": git_repo,
        "live": live,
        "keep_path": KEEP_PATH,
        "abandoned_path": ABANDONED_PATH,
        "lost_path": LOST_PATH,
        "never_committed": NEVER_COMMITTED,
        "salvage_rel": SALVAGE_REL,
        "changelog": live / CHANGELOG,
        "keep_sha256": keep_sha,
        "abandoned_sha256": abandoned_sha,
        "lost_sha256": lost_sha,
        "keep_bytes": len(lf(KEEP_BODY)),
        "abandoned_bytes": len(lf(ABANDONED_BODY)),
        "lost_bytes": len(lf(LOST_BODY)),
        "head": head,
    }
