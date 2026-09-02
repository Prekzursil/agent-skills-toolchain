#!/usr/bin/env python3
"""Read-only probe of host live harness trees. Never writes."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from rollback import fingerprint_path


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parents[3]


def host_candidates() -> list[Path]:
    home = Path.home()
    repo = repo_root()
    return [
        repo / "rules",
        home / ".claude",
        home / ".claude" / "rules",
        home / ".claude",
        home / ".claude" / "rules",
        home / ".cursor" / "rules",
        home / ".agents",
        home / ".cursor" / "rules",
    ]


def host_census() -> dict[str, Any]:
    rows = []
    present = 0
    for p in host_candidates():
        rec = fingerprint_path(p)
        rec["file_count"] = rec.get("file_count", 1 if rec.get("is_file") else 0)
        if rec["exists"] and rec.get("file_count", 0) > 0:
            present += 1
        rows.append(rec)
    return {
        "present_nonempty_trees": present,
        "note": (
            "This Linux worktree does not carry the 2026-08-09 Windows live estate. "
            "Host trees are fingerprinted read-only; CNF-0045 never writes them."
        ),
        "rows": rows,
    }
