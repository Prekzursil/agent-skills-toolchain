#!/usr/bin/env python3
"""Shared sample bound for AUD-0003 PR-history census probes.

Bound (documented, not silent truncation):
  - 12 most recently updated MERGED PRs targeting any base (via `gh pr list
    --state merged --limit 12`, sorted by GitHub's updatedAt desc).
  - 8 most recently updated CLOSED-without-merge PRs (walk `gh api
    .../pulls?state=closed&sort=updated&direction=desc` until 8 with
    merged_at=null are collected, max 5 pages / 150 closed PRs scanned).

Full closed history on this repo is ~310 PRs (Link: rel=last page=310 at
per_page=1). Residual: PRs outside this 20-row window are NOT-CHECKED.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any

REPO = "Prekzursil/agent-skills-toolchain"
MERGED_LIMIT = 12
CLOSED_UNMERGED_LIMIT = 8
CLOSED_SCAN_PAGES = 5
CLOSED_PAGE_SIZE = 30
MAIN_REF = "origin/main"


def run(cmd: list[str], timeout: int = 120) -> tuple[int, str]:
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"TIMEOUT: {' '.join(cmd)}"
    except OSError as e:
        return 127, f"{type(e).__name__}: {e}"


def gh_json(args: list[str]) -> Any:
    rc, out = run(["gh", *args])
    if rc != 0:
        raise RuntimeError(f"gh failed rc={rc}: {out[:2000]}")
    return json.loads(out)


def selection_meta() -> dict:
    return {
        "bound_description": (
            f"{MERGED_LIMIT} most-recently-updated merged PRs + "
            f"{CLOSED_UNMERGED_LIMIT} most-recently-updated closed-without-merge "
            f"PRs (closed scan: up to {CLOSED_SCAN_PAGES} pages x "
            f"{CLOSED_PAGE_SIZE})"
        ),
        "merged_limit": MERGED_LIMIT,
        "closed_unmerged_limit": CLOSED_UNMERGED_LIMIT,
        "closed_scan_pages": CLOSED_SCAN_PAGES,
        "main_ref": MAIN_REF,
        "selection_method": (
            "gh pr list --state merged --limit N; gh api pulls?state=closed "
            "filtered to merged_at=null"
        ),
        "full_history_note": (
            "Repo has ~310 closed PRs (API Link last=page 310 at per_page=1). "
            "Anything outside this bound is residual_unknown / NOT-CHECKED."
        ),
    }


def load_sample() -> list[dict]:
    """Return the bounded PR sample as normalized dicts."""
    merged_raw = gh_json(
        [
            "pr",
            "list",
            "--repo",
            REPO,
            "--state",
            "merged",
            "--limit",
            str(MERGED_LIMIT),
            "--json",
            "number,title,state,mergedAt,mergeCommit,headRefOid,baseRefName,"
            "closedAt,updatedAt",
        ]
    )
    merged: list[dict] = []
    for p in merged_raw:
        mc = p.get("mergeCommit") or {}
        merged.append(
            {
                "number": p["number"],
                "title": p["title"],
                "gh_state": p["state"],
                "sample_class": "merged",
                "merged_at": p.get("mergedAt"),
                "merge_commit_sha": mc.get("oid") if isinstance(mc, dict) else None,
                "head_sha": p["headRefOid"],
                "base_ref": p["baseRefName"],
                "closed_at": p.get("closedAt"),
                "updated_at": p.get("updatedAt"),
            }
        )

    closed_unmerged: list[dict] = []
    pages_scanned = 0
    for page in range(1, CLOSED_SCAN_PAGES + 1):
        pages_scanned = page
        batch = gh_json(
            [
                "api",
                f"repos/{REPO}/pulls?state=closed&per_page={CLOSED_PAGE_SIZE}"
                f"&sort=updated&direction=desc&page={page}",
            ]
        )
        if not batch:
            break
        for p in batch:
            if p.get("merged_at") is not None:
                continue
            closed_unmerged.append(
                {
                    "number": p["number"],
                    "title": p["title"],
                    "gh_state": "CLOSED",
                    "sample_class": "closed_unmerged",
                    "merged_at": None,
                    "merge_commit_sha": p.get("merge_commit_sha"),
                    "head_sha": p["head"]["sha"],
                    "base_ref": p["base"]["ref"],
                    "closed_at": p.get("closed_at"),
                    "updated_at": p.get("updated_at"),
                }
            )
            if len(closed_unmerged) >= CLOSED_UNMERGED_LIMIT:
                break
        if len(closed_unmerged) >= CLOSED_UNMERGED_LIMIT:
            break

    sample = merged + closed_unmerged
    for row in sample:
        row["pages_scanned_for_closed"] = pages_scanned
    return sample


def ensure_head_fetched(head_sha: str, pr_number: int) -> tuple[bool, str]:
    """Make sure head_sha is a local commit object; fetch PR head if needed."""
    rc, _ = run(["git", "cat-file", "-e", f"{head_sha}^{{commit}}"])
    if rc == 0:
        return True, "already-local"
    rc, out = run(
        [
            "git",
            "fetch",
            "origin",
            f"pull/{pr_number}/head:refs/remotes/origin/pr-{pr_number}",
        ]
    )
    if rc != 0:
        return False, out[:500]
    rc2, _ = run(["git", "cat-file", "-e", f"{head_sha}^{{commit}}"])
    return (
        rc2 == 0,
        "fetched-pr-head" if rc2 == 0 else f"fetch-ok-but-sha-missing:{out[:200]}",
    )


def pr_files(pr_number: int) -> list[str]:
    files = gh_json(["api", f"repos/{REPO}/pulls/{pr_number}/files", "--paginate"])
    # --paginate may return a list or concatenated; normalize
    if isinstance(files, dict):
        files = [files]
    return [f["filename"] for f in files if isinstance(f, dict) and "filename" in f]


def git_diff_name_only(head: str, main: str) -> list[str]:
    rc, out = run(["git", "diff", head, main, "--name-only"])
    if rc != 0:
        raise RuntimeError(f"git diff failed: {out[:1000]}")
    return [ln for ln in out.splitlines() if ln.strip()]


def is_ancestor(commit: str, tip: str) -> tuple[bool, str]:
    """Return (is_ancestor, note). Missing objects → False with note."""
    rc, _ = run(["git", "cat-file", "-e", f"{commit}^{{commit}}"])
    if rc != 0:
        # try fetch the sha
        run(["git", "fetch", "origin", commit])
        rc, _ = run(["git", "cat-file", "-e", f"{commit}^{{commit}}"])
        if rc != 0:
            return False, "object-absent"
    rc, _ = run(["git", "merge-base", "--is-ancestor", commit, tip])
    if rc == 0:
        return True, "ancestor-of-main"
    return False, "not-ancestor-of-main"


if __name__ == "__main__":
    meta = selection_meta()
    sample = load_sample()
    print(
        json.dumps(
            {
                "meta": meta,
                "count": len(sample),
                "numbers": [p["number"] for p in sample],
            },
            indent=2,
        )
    )
