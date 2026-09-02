#!/usr/bin/env python3
"""Probe 2: guard reads three-dot, not working-tree two-dot."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center" / "lib"))
sys.path.insert(0, str(HERE))

from fixtures import build_fresh, dirty_working_tree, git  # noqa: E402
from stale_branch_guard import evaluate  # noqa: E402


def _numstat_deletes(repo: Path, spec: str) -> list[str]:
    raw = git(repo, "diff", "--name-status", spec, check=False)
    deleted: list[str] = []
    for line in raw.splitlines():
        parts = line.split("\t")
        if parts and parts[0].startswith("D") and len(parts) >= 2:
            deleted.append(parts[-1])
    return deleted


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0469-p2-") as tmp:
        repo = build_fresh(Path(tmp))
        wt_deleted = dirty_working_tree(repo, n_delete=4)
        if len(wt_deleted) < 3:
            print("FAILED:IMP-0469-probe2 could not plant working-tree deletions")
            return 1

        three_dot_deletes = _numstat_deletes(repo, "origin/main...HEAD")
        two_dot_commit_deletes = _numstat_deletes(repo, "origin/main..HEAD")
        two_dot_wt_deletes = _numstat_deletes(repo, "origin/main")

        report = evaluate(repo, base="origin/main", head="HEAD")

    if "..." not in report.proposal.command:
        print("FAILED:IMP-0469-probe2 proposal command lacks three-dot token")
        print(report.proposal.command)
        return 1
    proposal_cmds = [c for c in report.commands if c.startswith("git diff")]
    three_cmds = [c for c in proposal_cmds if "..." in c]
    if not three_cmds:
        print("FAILED:IMP-0469-probe2 no git diff command used three-dot")
        print(report.commands)
        return 1
    if report.range_syntax != "three-dot":
        print("FAILED:IMP-0469-probe2 range_syntax", report.range_syntax)
        return 1

    if set(report.proposal.deleted_paths) != set(three_dot_deletes):
        print("FAILED:IMP-0469-probe2 proposal deletes != live three-dot")
        print("guard", report.proposal.deleted_paths)
        print("live", three_dot_deletes)
        return 1
    if report.proposal.deleted_paths != []:
        print("FAILED:IMP-0469-probe2 freshly-based three-dot should have 0 deletes")
        return 1

    if set(two_dot_wt_deletes) == set(three_dot_deletes):
        print("FAILED:IMP-0469-probe2 working-tree two-dot did not differ (control dead)")
        return 1
    if not (set(wt_deleted) <= set(two_dot_wt_deletes)):
        print("FAILED:IMP-0469-probe2 planted WT deletes missing from two-dot-vs-WT")
        print("planted", wt_deleted, "wt", two_dot_wt_deletes)
        return 1
    if set(wt_deleted) & set(report.proposal.deleted_paths):
        print("FAILED:IMP-0469-probe2 guard treated working-tree deletes as proposal")
        return 1

    if set(report.two_dot_commit.deleted_paths) != set(two_dot_commit_deletes):
        print("FAILED:IMP-0469-probe2 two-dot commit deletes mismatch")
        return 1
    if set(report.two_dot_working_tree.deleted_paths) != set(two_dot_wt_deletes):
        print("FAILED:IMP-0469-probe2 two-dot WT deletes mismatch")
        return 1
    if not report.two_dot_differs_from_three_dot:
        print("FAILED:IMP-0469-probe2 two-dot did not differ from three-dot")
        return 1
    if report.blocked:
        print("FAILED:IMP-0469-probe2 dirty WT on a fresh branch must not block")
        print(json.dumps(report.as_dict(), indent=2)[:2500])
        return 1
    if report.never_touched_deletion_count != 0:
        print(
            "FAILED:IMP-0469-probe2 never-touched "
            f"{report.never_touched_deletion_count} (WT noise leaked into gate)"
        )
        return 1

    out = {
        "probe": "probe2-three-dot-control",
        "unit_id": "IMP-0469",
        "range_syntax": report.range_syntax,
        "proposal_command": report.proposal.command,
        "three_dot_deletes": three_dot_deletes,
        "two_dot_commit_deletes": two_dot_commit_deletes,
        "two_dot_working_tree_deletes": two_dot_wt_deletes,
        "planted_working_tree_deletes": wt_deleted,
        "guard_used_three_dot": True,
        "working_tree_noise_excluded": True,
        "fresh_still_allowed": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"three_dot_deletes={len(three_dot_deletes)} "
        f"wt_two_dot_deletes={len(two_dot_wt_deletes)} "
        f"proposal_cmd={report.proposal.command}"
    )
    print("SUCCESS:IMP-0469-probe2 guard reads three-dot, ignores working-tree two-dot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
