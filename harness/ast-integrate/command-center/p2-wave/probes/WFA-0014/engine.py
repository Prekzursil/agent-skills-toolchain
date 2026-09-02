"""WFA-0014 dual-signal branch sweep.

Signal A: `git diff --name-only origin/main...<branch>` (three dots),
restricted to workflow-bearing paths. Working-tree files cannot enter.

Signal B: byte compare of each candidate against main's blob for the same
path via `git cat-file -p`. Ancestry is not authoritative: squash-merge
makes a fully merged branch report as ahead.

Conflict surface is the count of same-path byte mismatches, not the size
of an additions-only three-dot name list. This unit never recommends
deletion.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from gitcmd import (
    ahead_count,
    cat_file_p,
    is_git_repo,
    ls_tree_names,
    pick_main,
    remote_branches,
    rev_exists,
    three_dot_names,
    two_tree_names,
)
from paths import posix, workflow_bearing

LARGE_MODIFIED_FLOOR = 8
CLASS_UNIQUE = "GENUINELY-UNIQUE"
CLASS_IDENTICAL = "IDENTICAL-TO-MAIN"
CLASS_SUPERSEDED = "SUPERSEDED-DIFFERENT-NAME"


def sha256_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def conflict_surface(modified_count: int, added_count: int) -> str:
    if modified_count >= LARGE_MODIFIED_FLOOR:
        return "LARGE"
    if modified_count > 0:
        return "SMALL"
    if added_count > 0:
        return "ADDITIONS-ONLY"
    return "NONE"


def _main_index(repo: Path, main: str) -> tuple[dict[str, bytes], dict[str, list[str]]]:
    by_path: dict[str, bytes] = {}
    by_hash: dict[str, list[str]] = {}
    for path in ls_tree_names(repo, main):
        if not workflow_bearing(path):
            continue
        blob = cat_file_p(repo, main, path)
        if blob is None:
            continue
        by_path[path] = blob
        by_hash.setdefault(sha256_bytes(blob), []).append(path)
    return by_path, by_hash


def classify_path(
    path: str,
    branch_blob: bytes | None,
    main_by_path: dict[str, bytes],
    main_by_hash: dict[str, list[str]],
) -> dict[str, Any] | None:
    path = posix(path)
    if branch_blob is None:
        return None
    digest = sha256_bytes(branch_blob)
    main_same = main_by_path.get(path)
    elsewhere = [p for p in main_by_hash.get(digest, []) if p != path]
    same_path_equal = main_same is not None and main_same == branch_blob
    if main_same is None:
        role = "addition"
        cls = CLASS_SUPERSEDED if elsewhere else CLASS_UNIQUE
    elif same_path_equal:
        role = "squash-illusion"
        cls = CLASS_IDENTICAL
    else:
        role = "modification"
        cls = CLASS_SUPERSEDED if elsewhere else CLASS_UNIQUE
    return {
        "path": path,
        "classification": cls,
        "signal_a": True,
        "signal_b_same_path_equal": bool(same_path_equal),
        "signal_b_elsewhere_paths": elsewhere,
        "conflict_role": role,
        "blob_sha256": digest,
        "bytes": len(branch_blob),
        "deletion_recommended": False,
    }


def sweep_branch(repo: Path, main: str, branch: str, *, name: str | None = None) -> dict[str, Any]:
    label = name or branch
    names_a = [posix(p) for p in three_dot_names(repo, main, branch) if workflow_bearing(p)]
    names_two_tree = [posix(p) for p in two_tree_names(repo, main, branch) if workflow_bearing(p)]
    main_by_path, main_by_hash = _main_index(repo, main)
    hits: list[dict[str, Any]] = []
    unique: list[dict[str, Any]] = []
    superseded: list[dict[str, Any]] = []
    identical: list[dict[str, Any]] = []
    added = 0
    modified = 0
    for path in names_a:
        rec = classify_path(path, cat_file_p(repo, branch, path), main_by_path, main_by_hash)
        if rec is None:
            continue
        rec["branch"] = label
        hits.append(rec)
        if rec["conflict_role"] == "addition":
            added += 1
        elif rec["conflict_role"] == "modification":
            modified += 1
        if rec["classification"] == CLASS_UNIQUE:
            unique.append(rec)
        elif rec["classification"] == CLASS_SUPERSEDED:
            superseded.append(rec)
        elif rec["classification"] == CLASS_IDENTICAL:
            identical.append(rec)
    ahead = ahead_count(repo, main, branch)
    surface = conflict_surface(modified, added)
    return {
        "branch": label,
        "ref": branch,
        "ancestry_ahead": ahead > 0,
        "ahead_commit_count": ahead,
        "signal_a_path_count": len(names_a),
        "signal_a_paths": names_a,
        "two_tree_path_count": len(names_two_tree),
        "unique_content_count": len(unique),
        "superseded_count": len(superseded),
        "identical_to_main_count": len(identical),
        "added_count": added,
        "modified_count": modified,
        "conflict_surface": surface,
        "deletion_recommended": False,
        "discovery_only": True,
        "hits": hits,
        "unique_hits": unique,
        "superseded_hits": superseded,
    }


def sweep_refs(repo: Path, main: str, refs: list[tuple[str, str]]) -> dict[str, Any]:
    branches = []
    all_hits: list[dict[str, Any]] = []
    unique_branches = []
    for label, ref in refs:
        if not rev_exists(repo, ref):
            continue
        if ref == main or label.endswith("/HEAD"):
            continue
        row = sweep_branch(repo, main, ref, name=label)
        branches.append(row)
        all_hits.extend(row["hits"])
        if row["unique_content_count"] > 0:
            unique_branches.append(label)
    return {
        "main_ref": main,
        "branch_count": len(branches),
        "branches": branches,
        "hits": all_hits,
        "branches_with_unique_content": unique_branches,
        "unique_content_total": sum(b["unique_content_count"] for b in branches),
        "any_deletion_recommended": any(b["deletion_recommended"] for b in branches),
    }


def sweep_live(repo: Path) -> dict[str, Any]:
    if not is_git_repo(repo):
        return {
            "present": False,
            "reason": "not-a-git-repo",
            "branch_count": 0,
            "branches": [],
            "hits": [],
            "branches_with_unique_content": [],
            "unique_content_total": 0,
            "any_deletion_recommended": False,
            "main_ref": None,
            "remote_ref_count": 0,
        }
    main = pick_main(repo)
    refs = remote_branches(repo)
    if main is None:
        return {
            "present": True,
            "reason": "main-ref-absent",
            "branch_count": 0,
            "branches": [],
            "hits": [],
            "branches_with_unique_content": [],
            "unique_content_total": 0,
            "any_deletion_recommended": False,
            "main_ref": None,
            "remote_ref_count": len(refs),
        }
    pairs = []
    for ref in refs:
        short = ref.replace("refs/remotes/", "")
        if short in {"origin/HEAD"} or ref == main:
            continue
        pairs.append((short, ref))
    truncated = False
    if len(pairs) > 200:
        pairs = pairs[:200]
        truncated = True
    out = sweep_refs(repo, main, pairs)
    out["present"] = True
    out["reason"] = "scanned"
    out["remote_ref_count"] = len(refs)
    out["truncated"] = truncated
    return out
