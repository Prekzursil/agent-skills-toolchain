#!/usr/bin/env python3
"""Three-dot vs two-dot change-surface auditor (spec 11322 / CNF-0029).

Three-dot (`integration...branch`) is the commit-to-commit proposal: merge-base
to branch tip. Two-dot commit (`integration..branch`) compares the two trees
and will list deletions of paths the integration branch gained after the fork.
Two-dot worktree (`git diff integration` on a dirty checkout) additionally
folds in uncommitted edits.

This module never runs git in the host worktree. Callers pass an isolated
repository path.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any


def git_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "CNF-0029",
            "GIT_AUTHOR_EMAIL": "cnf-0029@invalid.example",
            "GIT_COMMITTER_NAME": "CNF-0029",
            "GIT_COMMITTER_EMAIL": "cnf-0029@invalid.example",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_OPTIONAL_LOCKS": "0",
            "EMAIL": "cnf-0029@invalid.example",
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    return env


def git(repo: Path, *args: str, check: bool = True, extra_env: dict[str, str] | None = None) -> str:
    env = git_env()
    if extra_env:
        env.update(extra_env)
    cmd = ["git", "-C", str(repo), "-c", "core.hooksPath=/dev/null", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"git {list(args)} rc={proc.returncode} stderr={(proc.stderr or '').strip()[:800]}"
        )
    return proc.stdout or ""


def rev_parse(repo: Path, ref: str) -> str:
    return git(repo, "rev-parse", ref).strip()


def merge_base(repo: Path, integration: str, branch: str) -> str:
    return git(repo, "merge-base", integration, branch).strip()


def ls_tree_paths(repo: Path, ref: str) -> set[str]:
    text = git(repo, "ls-tree", "-r", "--name-only", ref)
    return {line for line in text.splitlines() if line}


def parse_numstat(text: str) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    insertions = 0
    deletions = 0
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        ins_s, del_s, path = parts[0], parts[1], parts[2]
        ins_n = 0 if ins_s == "-" else int(ins_s)
        del_n = 0 if del_s == "-" else int(del_s)
        files.append({"path": path, "insertions": ins_n, "deletions": del_n})
        insertions += ins_n
        deletions += del_n
    return {
        "file_count": len(files),
        "insertions": insertions,
        "deletions": deletions,
        "files": files,
    }


def parse_name_status(text: str) -> dict[str, list[str]]:
    added: list[str] = []
    removed: list[str] = []
    changed: list[str] = []
    for line in text.splitlines():
        if "\t" not in line:
            continue
        status, path = line.split("\t", 1)
        code = status.strip()[:1]
        if code == "A":
            added.append(path)
        elif code == "D":
            removed.append(path)
        else:
            changed.append(path)
    return {"added": added, "removed": removed, "changed": changed}


def surface_from_spec(repo: Path, spec: str) -> dict[str, Any]:
    num = parse_numstat(git(repo, "diff", "--numstat", spec))
    names = parse_name_status(git(repo, "diff", "--name-status", spec))
    out = dict(num)
    out.update(names)
    out["spec"] = spec
    out["empty"] = num["file_count"] == 0 and num["deletions"] == 0 and num["insertions"] == 0
    return out


def would_revert_paths(repo: Path, integration: str, branch: str, mb: str) -> list[str]:
    """Paths the integration tip gained after merge-base that the branch lacks.

    Two-dot tree compare treats these as deletions. Three-dot does not, because
    they were never in the merge-base. Listing them is the would-revert signal.
    """
    gained = ls_tree_paths(repo, integration) - ls_tree_paths(repo, mb)
    missing = gained - ls_tree_paths(repo, branch)
    return sorted(missing)


def measure_branch(
    repo: Path,
    integration: str,
    branch: str,
    intended_paths: list[str] | None = None,
) -> dict[str, Any]:
    integ_sha = rev_parse(repo, integration)
    branch_sha = rev_parse(repo, branch)
    mb = merge_base(repo, integration, branch)
    three = surface_from_spec(repo, f"{integration}...{branch}")
    two = surface_from_spec(repo, f"{integration}..{branch}")
    revert = would_revert_paths(repo, integration, branch, mb)
    three_paths = set(three["added"] + three["removed"] + three["changed"])
    two_paths = set(two["added"] + two["removed"] + two["changed"])
    intended = list(intended_paths or [])
    intended_set = set(intended)
    return {
        "branch": branch,
        "integration": integration,
        "integration_sha": integ_sha,
        "branch_sha": branch_sha,
        "merge_base_sha": mb,
        "three_dot": three,
        "two_dot": two,
        "would_revert": revert,
        "would_revert_count": len(revert),
        "author_intended_paths": intended,
        "three_dot_matches_author": bool(intended) and three_paths == intended_set,
        "two_dot_matches_author": bool(intended) and two_paths == intended_set,
        "two_dot_hides_working_tree": False,
        "stale_branch_would_revert": len(revert) > 0,
        "surfaces_differ": (
            three["file_count"] != two["file_count"] or three["deletions"] != two["deletions"]
        ),
    }


def measure_worktree_two_dot(repo: Path, integration: str) -> dict[str, Any]:
    """Two-dot against the working tree (`git diff integration`), current HEAD."""
    head = rev_parse(repo, "HEAD")
    surface = surface_from_spec(repo, integration)
    surface["head_sha"] = head
    surface["form"] = "two-dot-worktree"
    return surface


def checkout(repo: Path, ref: str) -> None:
    git(repo, "checkout", "-q", ref)


def is_empty_surface(surface: dict[str, Any]) -> bool:
    return bool(surface.get("empty")) and int(surface.get("file_count") or 0) == 0
