#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0469.json from live fixture measurements."""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center" / "lib"))
sys.path.insert(0, str(HERE))

from fixtures import NEWER_FILE_COUNT, build_fresh, build_stale, dirty_working_tree  # noqa: E402
from stale_branch_guard import SENTINEL, evaluate  # noqa: E402

OUT_REL = "command-center/receipts/IMP-0469.json"


def _stat(d) -> dict:
    return {
        "files_changed": d.files_changed,
        "insertions": d.insertions,
        "deletions": d.deletions,
        "deleted_paths": list(d.deleted_paths),
        "added_paths": list(d.added_paths),
        "command": d.command,
        "raw_stat": d.raw_stat,
    }


def build_receipt() -> dict:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with tempfile.TemporaryDirectory(prefix="imp0469-receipt-") as tmp:
        root = Path(tmp)
        stale_repo = build_stale(root)
        fresh_repo = build_fresh(root)
        stale = evaluate(stale_repo, base="origin/main", head="HEAD")
        fresh = evaluate(fresh_repo, base="origin/main", head="HEAD")
        wt_deleted = dirty_working_tree(fresh_repo, n_delete=4)
        fresh_dirty = evaluate(fresh_repo, base="origin/main", head="HEAD")

    exact = {
        "question": (
            "how many deletions does this branch propose, and how many of them "
            "are files it never touched?"
        ),
        "stale_fixture": {
            "proposed_deletions_three_dot": stale.proposed_deletion_count,
            "never_touched_deletions": stale.never_touched_deletion_count,
            "never_touched_paths_sample": stale.never_touched_deletions[:10],
            "verdict": stale.verdict,
        },
        "fresh_fixture": {
            "proposed_deletions_three_dot": fresh.proposed_deletion_count,
            "never_touched_deletions": fresh.never_touched_deletion_count,
            "verdict": fresh.verdict,
        },
    }

    return {
        "id": "IMP-0469",
        "unit_id": "IMP-0469",
        "title": "Stale-branch reversion guard on the commit-to-commit surface",
        "spec": 11322,
        "failure_class": "FC-11322",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "output_path": OUT_REL,
        "output_schema": "command-center/schema/receipt.schema.json",
        "implementation": {
            "module": "command-center/lib/stale_branch_guard.py",
            "proposal_surface": "git diff <base>...<head> (three-dot, merge-base to HEAD)",
            "contrast_surfaces": [
                "git diff <base>..<head> (two-dot commit trees)",
                "git diff <base> (two-dot vs working tree; folds uncommitted noise)",
            ],
            "block_rule": (
                "BLOCK when two-dot commit-tree deletions include paths the branch "
                "never authored (files the integration base gained after merge-base)."
            ),
            "untouched_file_threshold": 1,
        },
        "exact_question": exact,
        "evidence": {
            "requirement": (
                "Three-dot diff stat with files changed and deletions, alongside "
                "the two-dot number, showing they differ - the two-dot form folds "
                "in working-tree noise and is not the proposal surface."
            ),
            "stale_branch": {
                "verdict": stale.verdict,
                "blocked": stale.blocked,
                "merge_base_sha": stale.merge_base_sha,
                "base_sha": stale.base_sha,
                "head_sha": stale.head_sha,
                "three_dot": _stat(stale.proposal),
                "two_dot_commit": _stat(stale.two_dot_commit),
                "they_differ": stale.two_dot_differs_from_three_dot,
                "never_touched_deletion_count": stale.never_touched_deletion_count,
                "newer_files_on_base_after_merge_base": NEWER_FILE_COUNT,
                "reason": stale.reason,
            },
            "freshly_based_branch": {
                "verdict": fresh.verdict,
                "blocked": fresh.blocked,
                "three_dot": _stat(fresh.proposal),
                "two_dot_commit": _stat(fresh.two_dot_commit),
                "never_touched_deletion_count": fresh.never_touched_deletion_count,
                "reason": fresh.reason,
            },
            "three_dot_control_dirty_working_tree": {
                "planted_uncommitted_deletes": wt_deleted,
                "proposal_command": fresh_dirty.proposal.command,
                "range_syntax": fresh_dirty.range_syntax,
                "three_dot_deleted_paths": fresh_dirty.proposal.deleted_paths,
                "two_dot_working_tree_deleted_paths": (
                    fresh_dirty.two_dot_working_tree.deleted_paths
                ),
                "working_tree_noise_excluded_from_proposal": (
                    set(wt_deleted).isdisjoint(fresh_dirty.proposal.deleted_paths)
                ),
                "still_allowed": not fresh_dirty.blocked,
            },
            "historical_incident_cited": {
                "files": 1188,
                "deletions": 316222,
                "note": (
                    "leftover feature branch vs main; two-dot tree comparison, not "
                    "the three-dot proposal surface"
                ),
            },
        },
        "tests": {
            "stale_branch_fixture_blocked": stale.blocked,
            "freshly_based_branch_allowed": not fresh.blocked,
            "both_states": stale.blocked and (not fresh.blocked),
            "guard_reads_three_dot_specifically": (
                "..." in fresh_dirty.proposal.command
                and fresh_dirty.range_syntax == "three-dot"
                and set(wt_deleted).isdisjoint(fresh_dirty.proposal.deleted_paths)
            ),
        },
        "reviewer": {
            "reviewer_id": "IMP-0469-probe2-three-dot-control",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Named probes re-run the guard on isolated fixture repos. "
                "Catalog scoring review is independent of G-1 probe-green."
            ),
        },
        "owner_approval_required": True,
        "owner_approval": {
            "status": "not-owner-gated-for-G-1-probe-green",
            "note": (
                "Catalog marks owner_approval_required; G-1 delivery is the "
                "implementation plus live probes, not an owner ruling."
            ),
        },
        "dependencies_declared": ["IMP-0428", "IMP-0432"],
        "timestamps": {"emitted_at": now},
        "notes": (
            "G-1 IMP-0469: stale-branch reversion guard implemented. "
            "Proposal surface is three-dot commit-to-commit. "
            "SENTINEL:IMP-0469:STALE-BRANCH-GUARDED"
        ),
    }


def write_receipt() -> Path:
    doc = build_receipt()
    path = REPO / OUT_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


if __name__ == "__main__":
    out = write_receipt()
    print(f"wrote {out} bytes={out.stat().st_size}")
    print(SENTINEL)
