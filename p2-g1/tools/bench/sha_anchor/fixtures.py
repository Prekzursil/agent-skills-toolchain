"""Phase-0 fixture repo (TST-0302)."""
from __future__ import annotations

from pathlib import Path

from gitutil import commit_files, init_repo

PHASE0_FILES = {
    "cases/router.json": b'{"id":"router","n":3}\n',
    "cases/council.json": b'{"id":"council","n":2}\n',
    "README.md": b"# phase0\n",
}


def seed_phase0_repo(path: Path) -> str:
    init_repo(path)
    return commit_files(path, PHASE0_FILES, "phase0 seed")
