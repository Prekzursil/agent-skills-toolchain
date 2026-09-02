#!/usr/bin/env python3
"""Named probe 2: first stage boundary rollback in a scratch clone.

Reads git HEAD^{tree} equality after `git revert --no-edit HEAD`. Probe 1 reads
named-script coverage — a different field. Two scratch clones must agree.
Does not git-mutate the delivery worktree.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from estate import S1_EVALUATOR_REL  # noqa: E402
from rollback import (  # noqa: E402
    RESTORE_COMMAND,
    content_preservation_both_directions,
    two_clone_rehearsal,
)

ART = REPO / "command-center/phase3/A9/MIGRATION.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:ARC-0063-probe2 migration artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    rb = two_clone_rehearsal()
    preserve = content_preservation_both_directions()
    if not rb.get("pass"):
        print("FAILED:ARC-0063-probe2 rollback rehearsal")
        print(json.dumps(rb, indent=2, default=str)[:3000])
        return 1
    if rb.get("two_clone_readings_agree") is not True:
        print("FAILED:ARC-0063-probe2 two clone readings disagree (BLOCKED, not picked)")
        print(json.dumps(rb, indent=2, default=str)[:2000])
        return 1
    if not rb.get("baseline_tree_equals_post_revert"):
        print("FAILED:ARC-0063-probe2 post-revert tree != baseline")
        return 1
    if rb.get("first_stage_artifact_removed") != S1_EVALUATOR_REL:
        print("FAILED:ARC-0063-probe2 unexpected restored path")
        return 1
    if not preserve.get("pass"):
        print("FAILED:ARC-0063-probe2 content preservation both directions")
        print(json.dumps(preserve, indent=2, default=str)[:2000])
        return 1

    tests_block = doc.get("tests")
    if isinstance(tests_block, dict):
        recorded = tests_block.get("rollback_rehearsal") or {}
    else:
        recorded = (doc.get("report") or {}).get("rollback_rehearsal") or doc.get("rollback_rehearsal") or {}
    if recorded.get("stage_id") != "S1":
        print("FAILED:ARC-0063-probe2 artifact stage_id drift")
        return 1
    if recorded.get("scratch_clone") is not True:
        print("FAILED:ARC-0063-probe2 artifact did not record scratch clone")
        return 1
    if recorded.get("baseline_tree_equals_post_revert") is not True:
        print("FAILED:ARC-0063-probe2 artifact missing tree equality")
        return 1
    if recorded.get("first_stage_artifact_removed") != S1_EVALUATOR_REL:
        print("FAILED:ARC-0063-probe2 artifact path drift")
        return 1
    if RESTORE_COMMAND not in str(recorded.get("restore_command") or ""):
        print("FAILED:ARC-0063-probe2 artifact restore_command drift")
        return 1
    both = (doc.get("tests") or {}).get("content_preservation_both_directions") or {}
    if both.get("forward_prior_bytes_unchanged") is not True:
        print("FAILED:ARC-0063-probe2 artifact missing forward preservation")
        return 1
    if both.get("reverse_restores_pre_stage") is not True:
        print("FAILED:ARC-0063-probe2 artifact missing reverse restoration")
        return 1

    # Confirm the delivery worktree was not turned into a git operation target.
    git_dir = REPO / ".git"
    out = {
        "probe": "probe2-rollback-rehearsal",
        "unit_id": "ARC-0063",
        "stage_id": "S1",
        "scratch_clone": True,
        "baseline_tree_equals_post_revert": True,
        "two_clone_readings_agree": True,
        "first_stage_artifact_removed": S1_EVALUATOR_REL,
        "restore_command": RESTORE_COMMAND,
        "worktree_git_dir_present": git_dir.is_dir(),
        "pass": True,
        "field": "git-HEAD-tree-sha-after-revert",
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "scratch=True equal=True gone="
        f"{S1_EVALUATOR_REL} two_clones_agree=True "
        f"forward={preserve['forward_prior_bytes_unchanged']} "
        f"reverse={preserve['reverse_restores_pre_stage']}"
    )
    print("SUCCESS:ARC-0063-probe2 first-boundary rollback in scratch clone")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
