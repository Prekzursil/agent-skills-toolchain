#!/usr/bin/env python3
"""Live VCS census on this Linux box. Honest ABSENT — never invented SAFE-TO-RETIRE."""
from __future__ import annotations

import os
from pathlib import Path

NAMED_WORKTREES = [
    "agent-skills-toolchain",
    "ast-harness-reconcile",
    "ast-statusline-capture",
    "cookie-bridge-skill",
    "ast-increment1",
]

SEARCH_ROOTS = [
    Path("/opt/p2"),
    Path("/opt/p2/ast-integrate"),
]


def _has_git(path: Path) -> bool:
    g = path / ".git"
    return g.is_dir() or g.is_file()


def _walk_git(root: Path, max_depth: int) -> list[Path]:
    found: list[Path] = []
    if not root.is_dir():
        return found
    root = root.resolve()
    for dirpath, dirnames, _filenames in os.walk(root, followlinks=False):
        rel = Path(dirpath).resolve().relative_to(root)
        depth = 0 if str(rel) == "." else len(rel.parts)
        if depth >= max_depth:
            dirnames[:] = []
            continue
        if ".git" in dirnames or (Path(dirpath) / ".git").is_file():
            found.append(Path(dirpath).resolve())
            dirnames[:] = [d for d in dirnames if d != ".git"]
    return found


def find_git_repos() -> list[str]:
    seen: set[Path] = set()
    out: list[str] = []
    for root in SEARCH_ROOTS:
        for repo in _walk_git(root, max_depth=4):
            if repo in seen:
                continue
            seen.add(repo)
            out.append(str(repo))
    return sorted(out)


def named_worktree_rows() -> list[dict]:
    rows = []
    for name in NAMED_WORKTREES:
        hits: list[str] = []
        for root in SEARCH_ROOTS:
            cand = root / name
            if cand.exists():
                hits.append(str(cand.resolve()))
        present = bool(hits)
        rows.append(
            {
                "kind": "named-worktree",
                "name": name,
                "scope": "live",
                "verdict": "ABSENT-NOT-CHECKED" if not present else "UNPROVEN",
                "classified_unmerged": False,
                "empty_diff": False,
                "paths_found": hits,
                "reason": (
                    "Named NEEDS-OWNER-DECISION worktree is not on this Linux box; "
                    "recorded ABSENT-NOT-CHECKED, not SAFE-TO-RETIRE."
                    if not present
                    else "Path exists; byte comparison against the original estate retained tree is UNPROVEN here."
                ),
            }
        )
    return rows


def live_census(worktree: Path) -> dict:
    worktree = worktree.resolve()
    git_here = _has_git(worktree)
    repos = find_git_repos()
    objects = named_worktree_rows()
    objects.append(
        {
            "kind": "no-remote-repo",
            "name": str(worktree),
            "scope": "live",
            "verdict": "ABSENT-NOT-CHECKED" if not git_here else "UNPROVEN",
            "classified_unmerged": False,
            "empty_diff": False,
            "has_dot_git": git_here,
            "reason": (
                "This worktree has no .git; no live branch/tag/stash/worktree "
                "object store to compare."
                if not git_here
                else "Live git dir present; not treated as SAFE-TO-RETIRE without byte proof."
            ),
        }
    )
    return {
        "worktree": str(worktree),
        "worktree_is_git": git_here,
        "git_repos_found": repos,
        "objects": objects,
        "live_unique_unproven": [
            o for o in objects if o.get("verdict") in {"RETAIN", "UNPROVEN"}
        ],
    }
