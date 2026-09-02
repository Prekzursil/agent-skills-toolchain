#!/usr/bin/env python3
"""Content-level VCS-object classifier (byte comparison, never ancestry).

Ancestry (`rev-list --count retained..ref`) is recorded only as a witness that
squash-merge lies. Verdicts use `git ls-tree` blob maps. A failed comparison
is UNPROVEN and the object is retained. This module never deletes.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

GIT_ENV_BASE = {
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_OPTIONAL_LOCKS": "0",
}

SAFE = "SAFE-TO-RETIRE"
RETAIN = "RETAIN"
UNPROVEN = "UNPROVEN"
FOREIGN = "FOREIGN-WORKTREE"
STASH_EMPTY = "STASH-NO-UNIQUE-CONTENT"
ABSENT = "ABSENT-NOT-CHECKED"
STASH_SAVED_NOTHING = "STASH-PUSH-SAVED-NOTHING"


class GitError(RuntimeError):
    pass


def git(
    repo: Path,
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(GIT_ENV_BASE)
    p = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        env=env,
    )
    if check and p.returncode != 0:
        raise GitError(
            f"git {' '.join(args)} in {repo} rc={p.returncode} "
            f"err={(p.stderr or '')[-400:]}"
        )
    return p


def git_common_dir(repo: Path) -> Path:
    p = git(repo, "rev-parse", "--git-common-dir")
    raw = p.stdout.strip()
    d = Path(raw)
    if not d.is_absolute():
        d = (repo / d)
    return d.resolve()


def parse_ls_tree(text: str) -> dict[str, str]:
    blobs: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        meta, path = line.split("\t", 1)
        parts = meta.split()
        if len(parts) < 3 or parts[1] != "blob":
            continue
        blobs[path] = parts[2]
    return blobs


def blob_map(repo: Path, ref: str) -> dict[str, str]:
    p = git(repo, "ls-tree", "-r", "--full-tree", ref)
    return parse_ls_tree(p.stdout)


def content_diff(repo: Path, retained: str, obj: str) -> dict[str, Any]:
    try:
        a = blob_map(repo, retained)
        b = blob_map(repo, obj)
    except GitError as exc:
        return {
            "ok": False,
            "empty": False,
            "error": str(exc),
            "only_retained": [],
            "only_object": [],
            "changed": [],
        }
    only_a = sorted(set(a) - set(b))
    only_b = sorted(set(b) - set(a))
    changed = sorted(p for p in set(a) & set(b) if a[p] != b[p])
    empty = not only_a and not only_b and not changed
    return {
        "ok": True,
        "empty": empty,
        "only_retained": only_a,
        "only_object": only_b,
        "changed": changed,
        "retained_blob_count": len(a),
        "object_blob_count": len(b),
        "instrument": "git-ls-tree-blob-map",
    }


def ancestry_ahead(repo: Path, retained: str, obj: str) -> dict[str, Any]:
    p = git(repo, "rev-list", "--count", f"{retained}..{obj}", check=False)
    if p.returncode != 0:
        return {
            "ok": False,
            "ahead": False,
            "ahead_count": None,
            "error": (p.stderr or p.stdout or "")[-300:],
        }
    n = int((p.stdout or "0").strip() or "0")
    return {
        "ok": True,
        "ahead": n > 0,
        "ahead_count": n,
        "instrument": "git-rev-list-count",
        "note": (
            "Ancestry AHEAD is not a delete authorisation and is not UNMERGED. "
            "Squash-merge makes merged work report AHEAD on this estate."
        ),
    }


def classify_ref(
    repo: Path,
    *,
    kind: str,
    name: str,
    ref: str,
    retained: str = "main",
    scope: str = "control",
) -> dict[str, Any]:
    diff = content_diff(repo, retained, ref)
    anc = ancestry_ahead(repo, retained, ref)
    retained_path = f"{Path(repo).resolve()}:refs/heads/{retained}"
    if not diff.get("ok"):
        return {
            "kind": kind,
            "name": name,
            "ref": ref,
            "scope": scope,
            "verdict": UNPROVEN,
            "classified_unmerged": False,
            "empty_diff": False,
            "retained_path": retained_path,
            "byte_comparison": diff,
            "ancestry": anc,
            "reason": "content comparison failed; object retained (UNPROVEN)",
        }
    if diff["empty"]:
        return {
            "kind": kind,
            "name": name,
            "ref": ref,
            "scope": scope,
            "verdict": SAFE,
            "classified_unmerged": False,
            "empty_diff": True,
            "retained_path": retained_path,
            "byte_comparison": diff,
            "ancestry": anc,
            "reason": (
                "Blob map vs retained is empty. Ancestry AHEAD (if any) is "
                "ignored; this is SAFE-TO-RETIRE, not unmerged."
            ),
        }
    return {
        "kind": kind,
        "name": name,
        "ref": ref,
        "scope": scope,
        "verdict": RETAIN,
        "classified_unmerged": True,
        "empty_diff": False,
        "retained_path": retained_path,
        "byte_comparison": diff,
        "ancestry": anc,
        "reason": "content differs from retained tree; unique bytes, retain",
    }


def classify_stash(
    repo: Path,
    stash_ref: str,
    *,
    retained: str = "HEAD",
    scope: str = "control",
) -> dict[str, Any]:
    row = classify_ref(
        repo,
        kind="stash",
        name=stash_ref,
        ref=stash_ref,
        retained=retained,
        scope=scope,
    )
    third = git(repo, "rev-parse", "--verify", f"{stash_ref}^3", check=False)
    row["untracked_parent_present"] = third.returncode == 0
    if row["verdict"] == SAFE:
        row["verdict"] = STASH_EMPTY
        row["reason"] = (
            "Stash entry exists but its tree is byte-identical to retained; "
            "existence is not unique work."
        )
        # SAFE-TO-RETIRE schema branch requires classified_unmerged false
        # and empty_diff true — STASH-NO-UNIQUE-CONTENT is the named class
        # for "exists but nothing unique".
    return row


def classify_worktree(
    path: Path,
    expected_common_dir: Path,
    *,
    retained: str = "main",
    scope: str = "control",
) -> dict[str, Any]:
    path = path.resolve()
    if not (path / ".git").exists() and not (path / ".git").is_file():
        git_dir = path / ".git"
        if not git_dir.exists():
            return {
                "kind": "worktree",
                "name": str(path),
                "scope": scope,
                "verdict": UNPROVEN,
                "reason": "path is not a git worktree",
                "classified_unmerged": False,
                "empty_diff": False,
            }
    try:
        common = git_common_dir(path)
    except GitError as exc:
        return {
            "kind": "worktree",
            "name": str(path),
            "scope": scope,
            "verdict": FOREIGN,
            "git_common_dir": None,
            "expected_git_common_dir": str(expected_common_dir.resolve()),
            "reason": f"cannot read git-common-dir: {exc}",
            "classified_unmerged": False,
            "empty_diff": False,
            "spec_failure_class": FOREIGN,
        }
    expected = expected_common_dir.resolve()
    if common != expected:
        return {
            "kind": "worktree",
            "name": str(path),
            "scope": scope,
            "verdict": FOREIGN,
            "git_common_dir": str(common),
            "expected_git_common_dir": str(expected),
            "reason": (
                "Worktree git-common-dir is a different repository; named spec "
                "failure class FOREIGN-WORKTREE — not audited as ours."
            ),
            "classified_unmerged": False,
            "empty_diff": False,
            "spec_failure_class": FOREIGN,
        }
    head = git(path, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    row = classify_ref(
        path,
        kind="worktree",
        name=str(path),
        ref="HEAD",
        retained=retained,
        scope=scope,
    )
    row["git_common_dir"] = str(common)
    row["head_branch"] = head
    row["identity"] = "ours"
    return row


def list_branches(repo: Path) -> list[str]:
    p = git(repo, "for-each-ref", "--format=%(refname:short)", "refs/heads")
    return [ln.strip() for ln in p.stdout.splitlines() if ln.strip()]


def list_tags(repo: Path) -> list[str]:
    p = git(repo, "for-each-ref", "--format=%(refname:short)", "refs/tags")
    return [ln.strip() for ln in p.stdout.splitlines() if ln.strip()]


def list_stashes(repo: Path) -> list[str]:
    p = git(repo, "stash", "list", "--format=%gd", check=False)
    if p.returncode != 0:
        return []
    return [ln.strip() for ln in p.stdout.splitlines() if ln.strip()]


def list_worktrees(repo: Path) -> list[Path]:
    p = git(repo, "worktree", "list", "--porcelain")
    paths: list[Path] = []
    for line in p.stdout.splitlines():
        if line.startswith("worktree "):
            paths.append(Path(line[len("worktree ") :]))
    return paths


def remotes(repo: Path) -> list[str]:
    p = git(repo, "remote", check=False)
    if p.returncode != 0:
        return []
    return [ln.strip() for ln in p.stdout.splitlines() if ln.strip()]


def enumerate_repo(
    repo: Path,
    *,
    retained: str = "main",
    scope: str = "control",
    extra_worktree_paths: list[Path] | None = None,
) -> dict[str, Any]:
    repo = repo.resolve()
    common = git_common_dir(repo)
    objects: list[dict[str, Any]] = []
    remote_names = remotes(repo)
    objects.append(
        {
            "kind": "no-remote-repo",
            "name": str(repo),
            "scope": scope,
            "verdict": RETAIN if not remote_names else UNPROVEN,
            "remotes": remote_names,
            "no_remote": not remote_names,
            "reason": (
                "Repository has no remotes; listed, not deleted, not pushed."
                if not remote_names
                else f"remotes present: {remote_names}"
            ),
            "classified_unmerged": False,
            "empty_diff": False,
        }
    )
    for name in list_branches(repo):
        objects.append(
            classify_ref(
                repo,
                kind="branch",
                name=name,
                ref=name,
                retained=retained,
                scope=scope,
            )
        )
    for name in list_tags(repo):
        objects.append(
            classify_ref(
                repo,
                kind="tag",
                name=name,
                ref=name,
                retained=retained,
                scope=scope,
            )
        )
    for stash in list_stashes(repo):
        objects.append(
            classify_stash(repo, stash, retained=retained, scope=scope)
        )
    seen: set[Path] = set()
    for wt in list_worktrees(repo) + list(extra_worktree_paths or []):
        key = wt.resolve()
        if key in seen:
            continue
        seen.add(key)
        objects.append(
            classify_worktree(
                wt,
                common,
                retained=retained,
                scope=scope,
            )
        )
    return {
        "repo": str(repo),
        "git_common_dir": str(common),
        "retained": retained,
        "objects": objects,
        "deletions_performed": False,
    }
