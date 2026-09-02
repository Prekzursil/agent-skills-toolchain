#!/usr/bin/env python3
"""Discover pytest-style tests that BLD-0040 grades."""
from __future__ import annotations

from pathlib import Path

SKIP_PARTS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".tox",
}


def corpus_of(rel: str) -> str:
    posix = rel.replace("\\", "/")
    if "/probes/BLD-0040/" in posix:
        return "planted-control"
    if "/probes/" in posix:
        return "probe-fixture"
    if posix.startswith("tools/"):
        return "program"
    return "other"


def iter_test_files(repo: Path) -> list[Path]:
    found: set[Path] = set()
    for pat in ("test_*.py", "*_test.py"):
        for path in repo.rglob(pat):
            if any(part in SKIP_PARTS for part in path.parts):
                continue
            if not path.is_file():
                continue
            found.add(path.resolve())
    return sorted(found)


def registry_status(repo: Path) -> dict:
    rel = "command-center/TEST-REGISTRY.json"
    path = repo / rel
    return {
        "path": rel,
        "present": path.is_file() and path.stat().st_size > 0,
        "note": (
            "present"
            if path.is_file()
            else "absent on this worktree; census walks live test_*.py instead"
        ),
    }


iter_test_files = iter_test_files
corpus_of = corpus_of
registry_status = registry_status
