#!/usr/bin/env python3
"""Read-only probe of host live harness trees. Never writes."""
from __future__ import annotations

from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parents[3]


def host_candidates() -> list[Path]:
    home = Path.home()
    return [
        REPO / "rules",
        home / ".claude",
        home / ".claude" / "rules",
        Path("/root/.claude"),
        Path("/root/.claude/rules"),
        home / ".cursor" / "rules",
        Path("/root/.cursor/rules"),
    ]


def host_census() -> dict[str, Any]:
    rows = []
    present = 0
    for p in host_candidates():
        exists = p.exists()
        is_dir = p.is_dir()
        n = sum(1 for q in p.rglob("*") if q.is_file()) if is_dir else 0
        if exists and n > 0:
            present += 1
        rows.append(
            {
                "path": str(p),
                "exists": exists,
                "is_dir": is_dir,
                "file_count": n,
            }
        )
    return {
        "present_nonempty_trees": present,
        "note": (
            "This Linux worktree does not carry the 2026-08-09 Windows live "
            "estate. Host trees are fingerprinted read-only; IMP-0462 never "
            "writes them (owner_approval_required)."
        ),
        "rows": rows,
    }
