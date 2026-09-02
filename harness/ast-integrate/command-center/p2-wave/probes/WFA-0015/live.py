#!/usr/bin/env python3
"""Live host inventory for WFA-0015. Read-only. Never removes worktrees."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

NAMED_TREES = [
    "agent-skills-toolchain",
    "ast-harness-reconcile",
    "ast-statusline-capture",
    "cookie-bridge-skill",
    "ast-increment1",
]
SEARCH_ROOTS = [
    Path("/opt/p2"),
    Path("/opt"),
    Path("/root"),
    Path("/home"),
    Path("/tmp"),
]
SKIP_DIR_NAMES = {
    ".git",
    "__pycache__",
    "node_modules",
    ".cursor",
    "probes",
}


def _run(cmd: list[str], cwd: Path) -> dict:
    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"cmd": cmd, "rc": 99, "stdout": "", "stderr": str(exc)}
    return {
        "cmd": cmd,
        "rc": p.returncode,
        "stdout": (p.stdout or "")[-4000:],
        "stderr": (p.stderr or "")[-1000:],
    }


def find_named_trees() -> list[dict]:
    hits: list[dict] = []
    seen: set[str] = set()
    for root in SEARCH_ROOTS:
        if not root.is_dir():
            continue
        try:
            entries = list(root.iterdir())
        except OSError:
            continue
        # Shallow + one extra level only. A full rglob of /home is not needed
        # and would look like a sweep of unrelated tenants.
        candidates = list(entries)
        for ent in entries:
            if ent.is_dir():
                try:
                    candidates.extend(ent.iterdir())
                except OSError:
                    pass
        for p in candidates:
            if p.name in NAMED_TREES and p.is_dir():
                key = str(p)
                if key in seen:
                    continue
                seen.add(key)
                hits.append({"name": p.name, "path": key, "exists": True})
    missing = [
        {"name": n, "path": None, "exists": False}
        for n in NAMED_TREES
        if n not in {h["name"] for h in hits}
    ]
    return hits + missing


def live_inventory(repo: Path) -> dict:
    git_inside = _run(["git", "rev-parse", "--is-inside-work-tree"], repo)
    worktrees = _run(["git", "worktree", "list", "--porcelain"], repo)
    status = _run(["git", "status", "--porcelain=v1"], repo)
    git_dir = repo / ".git"
    named = find_named_trees()
    present = [n for n in named if n["exists"]]
    absent = [n for n in named if not n["exists"]]
    return {
        "host_root": str(repo),
        "git_available": git_inside.get("rc") == 0
        and "true" in (git_inside.get("stdout") or ""),
        "git_dot_exists": git_dir.exists(),
        "git_rev_parse": git_inside,
        "git_worktree_list": worktrees,
        "git_status": status,
        "named_needs_owner_trees": named,
        "named_present_count": len(present),
        "named_absent_count": len(absent),
        "removed_trees_recovered_from_reflog": [],
        "removed_trees_recovery": (
            "NOT-CHECKED: this checkout has no .git object store, so reflog "
            "and dangling objects for the 14 removed trees cannot be read here"
        ),
        "origin_refs_search": (
            "NOT-CHECKED: origin/* refs are unavailable (not a git repository)"
        ),
        "pr_merged_search": (
            "NOT-CHECKED: PR-MERGED state is unavailable without git remotes"
        ),
        "deletions_performed": [],
        "note": (
            "Live surface is this Linux copy of ast-integrate only. The original "
            "Windows 20-to-6 worktree cleanup is not mounted here. Unique-elsewhere "
            "for those 20 trees is therefore unproven on this host; the control "
            "estate in probes/WFA-0015 proves the classifier."
        ),
    }
