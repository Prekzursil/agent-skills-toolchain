"""Locate live 08/09 markdown+JSON pairs. Missing paths are unread, not invented."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

PAIR_08 = (
    "08-WORKFLOW-ARCHAEOLOGY-AND-SOURCE-CATALOG.md",
    "08-WORKFLOW-CANDIDATE-REGISTRY.json",
)
PAIR_09 = (
    "09-WORKFLOW-BLUEPRINT-LIBRARY.md",
    "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
)

CATALOG_ROOTS = (
    "C:/Users/Prekzursil/.claude/harness-restore-20260806",
    "/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806",
    "/c/Users/Prekzursil/.claude/harness-restore-20260806",
    str(Path.home() / ".claude/harness-restore-20260806"),
    "/root/.claude/harness-restore-20260806",
)


def _file(path: Path) -> bool:
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def search_roots() -> list[Path]:
    roots: list[Path] = []
    env = os.environ.get("WFA0011_SOURCE_ROOT")
    if env:
        roots.append(Path(env))
    roots.extend(Path(p) for p in CATALOG_ROOTS)
    roots.extend(
        [
            REPO,
            REPO / "command-center",
            REPO / "command-center" / "sources",
            REPO / "command-center" / "wfa",
            HERE / "fixtures" / "live",
        ]
    )
    return roots


def find_named(name: str) -> Path | None:
    env_key = "WFA0011_" + name.replace("-", "_").replace(".", "_").upper()
    env = os.environ.get(env_key)
    if env and _file(Path(env)):
        return Path(env)
    for root in search_roots():
        cand = root / name
        if _file(cand):
            return cand
    return None


def inspect_pair(md_name: str, json_name: str) -> dict[str, Any]:
    md = find_named(md_name)
    js = find_named(json_name)
    return {
        "markdown_name": md_name,
        "json_name": json_name,
        "markdown_path": None if md is None else str(md),
        "json_path": None if js is None else str(js),
        "markdown_present": md is not None,
        "json_present": js is not None,
        "pair_present": md is not None and js is not None,
        "unread_reason": None
        if (md is not None and js is not None)
        else "path-absent-on-this-worktree",
    }


def inspect_live() -> dict[str, Any]:
    p08 = inspect_pair(*PAIR_08)
    p09 = inspect_pair(*PAIR_09)
    unread: list[dict[str, Any]] = []
    for rec in (p08, p09):
        if not rec["pair_present"]:
            unread.append(
                {
                    "markdown": rec["markdown_name"],
                    "json": rec["json_name"],
                    "reason": rec["unread_reason"],
                    "invented": False,
                    "catalog_root": (
                        "C:/Users/Prekzursil/.claude/harness-restore-20260806"
                    ),
                }
            )
    return {
        "pair_08": p08,
        "pair_09": p09,
        "any_live_pair": bool(p08["pair_present"] or p09["pair_present"]),
        "unread": unread,
        "catalog_roots_tried": [str(p) for p in search_roots()],
    }
