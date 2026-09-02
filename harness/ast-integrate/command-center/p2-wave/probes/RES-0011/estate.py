#!/usr/bin/env python3
"""Two-signal census of agent/command trees on this Linux estate."""
from __future__ import annotations

import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Probe dir is command-center/p2-wave/probes/<id>/. HERE.parents[3] is repo root.
# __file__.parents[3] is command-center/ and misses repo-root agents/ commands/.
REPO = HERE.parents[3]

CANDIDATES = {
    "repo_agents": REPO / "agents",
    "repo_commands": REPO / "commands",
    "live_agents": Path.home() / ".claude" / "agents",
    "live_commands": Path.home() / ".claude" / "commands",
    "project_agents": REPO / ".claude" / "agents",
    "project_commands": REPO / ".claude" / "commands",
}


def _count_md(path: Path) -> int:
    if not path.is_dir():
        return 0
    return sum(1 for p in path.rglob("*.md") if p.is_file())


def census() -> dict:
    rows = {}
    for name, path in CANDIDATES.items():
        exists = path.is_dir()
        via_os = os.path.isdir(str(path))
        rows[name] = {
            "path": str(path),
            "is_dir_pathlib": exists,
            "is_dir_os": via_os,
            "signals_agree": exists == via_os,
            "md_count": _count_md(path) if exists else 0,
        }
    claude_cli = {
        "which": bool(_which("claude")),
        "path": _which("claude"),
    }
    return {
        "trees": rows,
        "any_tree_present": any(v["is_dir_pathlib"] for v in rows.values()),
        "claude_cli": claude_cli,
    }


def _which(name: str) -> str | None:
    for d in os.environ.get("PATH", "").split(os.pathsep):
        cand = Path(d) / name
        if cand.is_file() and os.access(cand, os.X_OK):
            return str(cand)
    return None
