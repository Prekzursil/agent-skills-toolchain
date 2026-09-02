#!/usr/bin/env python3
"""Locate 10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json on this estate.

The contracted program directory is NOT in this git tree. CC-0019 recorded
the file at 161,920 B under harness-restore-20260806 when that tree was
mounted; this Linux worktree may not have it. Absence is reported, not
forged into a fake original.
"""
from __future__ import annotations

from pathlib import Path

MAPS_NAME = "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json"
EXPECTED_BYTES_CC0019 = 161920


def repo_root(here: Path | None = None) -> Path:
    if here is None:
        here = Path(__file__).resolve().parent
    return here.parents[3]


def search_roots(repo: Path) -> list[Path]:
    home = Path.home()
    return [
        home / ".claude" / "harness-restore-20260806",
        Path("/root/.claude/harness-restore-20260806"),
        repo / "harness-restore-20260806",
        repo / "command-center" / "harness-restore-20260806",
        Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806"),
        Path("/c/Users/Prekzursil/.claude/harness-restore-20260806"),
        Path("C:/Users/Prekzursil/.claude/harness-restore-20260806"),
        repo,
        repo / "command-center",
        repo / "command-center" / "foundry",
        repo / "command-center" / "wfa",
    ]


def maps_candidates(repo: Path) -> list[str]:
    out: list[str] = []
    for root in search_roots(repo):
        out.append(str((root / MAPS_NAME).as_posix() if hasattr(root, "as_posix") else root / MAPS_NAME))
    return out


def find_maps(repo: Path) -> Path | None:
    direct = repo / MAPS_NAME
    if direct.is_file():
        return direct
    for root in search_roots(repo):
        cand = root / MAPS_NAME
        try:
            if cand.is_file() and cand.stat().st_size > 0:
                return cand
        except OSError:
            continue
    return None
