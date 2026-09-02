#!/usr/bin/env python3
"""Probe 1: stale-branch fixture blocked; freshly-based branch allowed."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center" / "lib"))
sys.path.insert(0, str(HERE))

from fixtures import NEWER_FILE_COUNT, build_fresh, build_stale  # noqa: E402
from stale_branch_guard import evaluate  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0469-p1-") as tmp:
        root = Path(tmp)
        stale_repo = build_stale(root)
        fresh_repo = build_fresh(root)
        stale = evaluate(stale_repo, base="origin/main", head="HEAD")
        fresh = evaluate(fresh_repo, base="origin/main", head="HEAD")

    if stale.range_syntax != "three-dot":
        print("FAILED:IMP-0469-probe1 guard range_syntax is not three-dot")
        return 1
    if "..." not in stale.proposal.command:
        print("FAILED:IMP-0469-probe1 proposal command is not three-dot")
        print(stale.proposal.command)
        return 1

    if not stale.blocked or stale.verdict != "BLOCK":
        print("FAILED:IMP-0469-probe1 stale fixture was not blocked")
        print(json.dumps(stale.as_dict(), indent=2)[:3000])
        return 1
    if stale.never_touched_deletion_count < NEWER_FILE_COUNT:
        print(
            "FAILED:IMP-0469-probe1 never-touched "
            f"{stale.never_touched_deletion_count} want>={NEWER_FILE_COUNT}"
        )
        return 1
    missing_newer = [
        f"newer_{i}.txt"
        for i in range(NEWER_FILE_COUNT)
        if f"newer_{i}.txt" not in stale.never_touched_deletions
    ]
    if missing_newer:
        print(f"FAILED:IMP-0469-probe1 stale missed newer files {missing_newer[:5]}")
        return 1
    if not stale.two_dot_differs_from_three_dot:
        print("FAILED:IMP-0469-probe1 stale three-dot equals two-dot (must differ)")
        return 1
    if stale.two_dot_commit.files_changed <= stale.proposal.files_changed:
        print(
            "FAILED:IMP-0469-probe1 two-dot files_changed "
            f"{stale.two_dot_commit.files_changed} not greater than three-dot "
            f"{stale.proposal.files_changed}"
        )
        return 1
    if stale.two_dot_commit.deletions <= stale.proposal.deletions:
        print(
            "FAILED:IMP-0469-probe1 two-dot deletions "
            f"{stale.two_dot_commit.deletions} not greater than three-dot "
            f"{stale.proposal.deletions}"
        )
        return 1
    if "feature.txt" not in stale.proposal.added_paths:
        print("FAILED:IMP-0469-probe1 three-dot missed the branch's own add")
        return 1

    if fresh.blocked or fresh.verdict != "ALLOW":
        print("FAILED:IMP-0469-probe1 freshly-based branch was blocked")
        print(json.dumps(fresh.as_dict(), indent=2)[:3000])
        return 1
    if fresh.never_touched_deletion_count != 0:
        print(
            "FAILED:IMP-0469-probe1 fresh never-touched "
            f"{fresh.never_touched_deletion_count} want=0"
        )
        return 1
    if fresh.proposed_deletion_count != 0:
        print(
            "FAILED:IMP-0469-probe1 fresh proposed deletions "
            f"{fresh.proposed_deletion_count} want=0"
        )
        return 1
    if "feature.txt" not in fresh.proposal.added_paths:
        print("FAILED:IMP-0469-probe1 fresh three-dot missed feature.txt")
        return 1

    out = {
        "probe": "probe1-both-states",
        "unit_id": "IMP-0469",
        "stale_blocked": True,
        "fresh_allowed": True,
        "stale_never_touched": stale.never_touched_deletion_count,
        "stale_three_dot_files": stale.proposal.files_changed,
        "stale_three_dot_deletions": stale.proposal.deletions,
        "stale_two_dot_files": stale.two_dot_commit.files_changed,
        "stale_two_dot_deletions": stale.two_dot_commit.deletions,
        "fresh_never_touched": fresh.never_touched_deletion_count,
        "merge_base_stale": stale.merge_base_sha,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"stale blocked never_touched={stale.never_touched_deletion_count} "
        f"three_dot_files={stale.proposal.files_changed} "
        f"two_dot_files={stale.two_dot_commit.files_changed}"
    )
    print(
        f"fresh allowed never_touched={fresh.never_touched_deletion_count} "
        f"three_dot_files={fresh.proposal.files_changed}"
    )
    print("SUCCESS:IMP-0469-probe1 stale blocked, freshly-based allowed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
