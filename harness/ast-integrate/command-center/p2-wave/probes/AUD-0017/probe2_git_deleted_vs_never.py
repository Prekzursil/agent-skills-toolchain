#!/usr/bin/env python3
"""Probe 2: git log --all --diff-filter=D for each live-only path.

Set difference cannot tell 'never in any repo' from 'deleted from history'.
This probe runs the deletion log on a planted pair: one path that was
committed then deleted, one path that was never added. Host worktree git
status is recorded; this Linux tree is not a git repo, so host live-only
files cannot be classified from history (and host live-only is empty).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from census import census  # noqa: E402
from git_history import (  # noqa: E402
    build_git_fixture,
    classify_live_only,
    host_git_status,
)

REPO = HERE.parents[3]


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0017-probe2 {msg}")
    return 1


def main() -> int:
    host_git = host_git_status(REPO)
    host = census(REPO, Path.home(), fixture=None)
    with tempfile.TemporaryDirectory(prefix="aud0017-p2-") as raw:
        planted = build_git_fixture(Path(raw))
        rows = classify_live_only(Path(planted["git_repo"]), planted["live_only"])
        by_rel = {r["rel"]: r for r in rows}
        deleted = by_rel.get("deleted.txt")
        never = by_rel.get("never.txt")
        if deleted is None or never is None:
            return fail(f"classification missing rows: {sorted(by_rel)}")
        if not deleted.get("was_deleted_in_history"):
            return fail(f"deleted.txt not seen as diff-filter=D: {deleted}")
        if not never.get("never_in_history"):
            return fail(f"never.txt not seen as never-in-history: {never}")
        if deleted.get("never_in_history"):
            return fail("deleted.txt misclassified as never-in-history")
        if never.get("was_deleted_in_history"):
            return fail("never.txt misclassified as deleted-in-history")

        host_class = []
        if host_git["is_git"]:
            host_class = classify_live_only(
                REPO,
                [row["rel"] for row in host["live_only"]],
            )
        payload = {
            "pass": True,
            "probe": "probe2-git-deleted-vs-never",
            "unit_id": "AUD-0017",
            "host_git": host_git,
            "host_live_only_count": host["counts"]["live_only"],
            "host_history_classified": host_class,
            "host_history_note": (
                "worktree is not a git repository; host live-only history is "
                "NOT-CHECKED (and host live-only is empty)"
                if not host_git["is_git"]
                else "host git present; classified each host live-only path"
            ),
            "fixture_live_only": planted["live_only"],
            "fixture_rows": rows,
            "distinct_from_probe1": (
                "probe1 is relative-path set difference after the deploy map; "
                "probe2 is git log --all --diff-filter=D on each live-only path"
            ),
        }
        print(json.dumps(payload, sort_keys=True, default=str))
        print(
            "deleted_was_D={0} never_in_history={1} host_git={2}".format(
                deleted["was_deleted_in_history"],
                never["never_in_history"],
                host_git["is_git"],
            )
        )
        print("SUCCESS:AUD-0017-probe2 git diff-filter=D distinguishes deleted vs never")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
