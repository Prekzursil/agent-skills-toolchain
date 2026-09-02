"""Discover live and repo skill trees on this worktree."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from common import REPO


def live_candidates() -> list[Path]:
    home = Path.home()
    return [
        home / ".claude" / "skills",
        home / ".agents" / "skills",
        Path("/root/.claude/skills"),
        Path("/root/.agents/skills"),
        Path("/home/ubuntu/.claude/skills"),
        Path("/home/ubuntu/.agents/skills"),
        REPO / ".claude" / "skills",
        REPO / ".agents" / "skills",
    ]


def repo_skill_tree() -> Path:
    return REPO / "skills"


def describe_tree(path: Path, role: str) -> dict[str, Any]:
    n = 0
    if path.is_dir():
        n = sum(
            1
            for p in path.rglob("*")
            if p.is_file() and p.suffix.lower() in {".md", ".markdown"}
        )
    return {
        "role": role,
        "path": str(path),
        "exists": path.exists(),
        "is_dir": path.is_dir(),
        "md_count": n,
    }


def host_skill_trees() -> list[dict[str, Any]]:
    rows = [describe_tree(repo_skill_tree(), "repo")]
    seen: set[str] = {str(repo_skill_tree())}
    for p in live_candidates():
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        rows.append(describe_tree(p, "live"))
    return rows


def grok_inspect_available() -> dict[str, Any]:
    import shutil

    path = shutil.which("grok")
    return {
        "binary_present": bool(path),
        "path": path,
        "note": (
            "grok inspect --json is absent on this Linux worktree; "
            "AUD-0058 uses the equivalent turn0-context-bag instrument."
            if not path
            else "grok binary present; AUD-0058 still uses the local bag instrument."
        ),
    }
