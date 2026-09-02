"""Locate catalog inputs. Missing paths become recall_limit, not invented refs."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

GRAPH_NAME = "08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json"
REGISTRY_NAME = "08-WORKFLOW-CANDIDATE-REGISTRY.json"

CATALOG_GRAPH = (
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
    "08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json"
)
CATALOG_REGISTRY = (
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
    "08-WORKFLOW-CANDIDATE-REGISTRY.json"
)

LIVE_SKILL_GLOBS = [
    "~/.claude/skills",
    "~/.agents/skills",
    "~/.claude/rules",
    "~/.claude/workflows",
    "skills/",
    "rules/",
    "tools/",
]


def _exists_file(path: Path) -> bool:
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def _exists_dir(path: Path) -> bool:
    try:
        return path.is_dir()
    except OSError:
        return False


def _home() -> Path:
    return Path.home()


def graph_candidates() -> list[Path]:
    home = _home()
    env = os.environ.get("WFA0002_GRAPH")
    out: list[Path] = []
    if env:
        out.append(Path(env))
    restore = Path("harness-restore-20260806")
    out.extend(
        [
            Path("C:/Users/Prekzursil/.claude") / restore / GRAPH_NAME,
            Path("/mnt/c/Users/Prekzursil/.claude") / restore / GRAPH_NAME,
            Path("/c/Users/Prekzursil/.claude") / restore / GRAPH_NAME,
            home / ".claude" / restore / GRAPH_NAME,
            Path("/root/.claude") / restore / GRAPH_NAME,
            REPO / "command-center" / GRAPH_NAME,
            HERE / GRAPH_NAME,
        ]
    )
    return out


def registry_candidates() -> list[Path]:
    home = _home()
    env = os.environ.get("WFA0002_REGISTRY")
    out: list[Path] = []
    if env:
        out.append(Path(env))
    restore = Path("harness-restore-20260806")
    out.extend(
        [
            Path("C:/Users/Prekzursil/.claude") / restore / REGISTRY_NAME,
            Path("/mnt/c/Users/Prekzursil/.claude") / restore / REGISTRY_NAME,
            Path("/c/Users/Prekzursil/.claude") / restore / REGISTRY_NAME,
            home / ".claude" / restore / REGISTRY_NAME,
            Path("/root/.claude") / restore / REGISTRY_NAME,
            REPO / "command-center" / REGISTRY_NAME,
        ]
    )
    return out


def live_skill_roots() -> list[tuple[str, Path]]:
    home = _home()
    return [
        ("live:~/.claude/skills", home / ".claude" / "skills"),
        ("live:~/.agents/skills", home / ".agents" / "skills"),
        ("live:~/.claude/rules", home / ".claude" / "rules"),
        ("live:~/.claude/workflows", home / ".claude" / "workflows"),
        ("repo:skills/", REPO / "skills"),
        ("repo:rules/", REPO / "rules"),
        ("repo:plugins/", REPO / "plugins"),
        ("repo:tools/", REPO / "tools"),
        ("repo:blueprints/workflows/", REPO / "blueprints" / "workflows"),
    ]


def first_existing_file(paths: list[Path]) -> Path | None:
    for p in paths:
        if _exists_file(p):
            return p
    return None


def git_head_available(repo: Path = REPO) -> bool:
    git_dir = repo / ".git"
    return git_dir.is_dir() or git_dir.is_file()


def inspect_live() -> dict[str, Any]:
    graph = first_existing_file(graph_candidates())
    registry = first_existing_file(registry_candidates())
    skill_roots = []
    for label, path in live_skill_roots():
        present = _exists_dir(path)
        file_count = 0
        if present:
            try:
                file_count = sum(1 for p in path.rglob("*") if p.is_file())
            except OSError:
                file_count = 0
        skill_roots.append(
            {
                "label": label,
                "path": str(path),
                "present": present,
                "file_count": file_count,
            }
        )
    unread: list[dict[str, Any]] = []
    if graph is None:
        unread.append(
            {
                "input": CATALOG_GRAPH,
                "reason": "path-absent-on-this-worktree",
                "invented": False,
            }
        )
    if registry is None:
        unread.append(
            {
                "input": CATALOG_REGISTRY,
                "reason": "path-absent-on-this-worktree",
                "invented": False,
            }
        )
    for row in skill_roots:
        if not row["present"] and row["label"].startswith("live:"):
            unread.append(
                {
                    "input": row["label"],
                    "reason": "path-absent-on-this-worktree",
                    "invented": False,
                }
            )
    return {
        "live_graph_path": None if graph is None else str(graph),
        "live_graph_present": graph is not None,
        "live_registry_path": None if registry is None else str(registry),
        "live_registry_present": registry is not None,
        "live_skill_roots": skill_roots,
        "git_head_available": git_head_available(),
        "git_head_note": (
            "worktree has no .git; evidence B for LIVE paths is git-absent. "
            "Fixture-control evidence B is the independent head-index, not a re-stat."
        ),
        "unread": unread,
        "catalog_live_globs": LIVE_SKILL_GLOBS,
    }
