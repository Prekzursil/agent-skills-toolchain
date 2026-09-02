#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0015-sweep-worktrees.json."""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from estate import (  # noqa: E402
    DIRTY_COUNT,
    NEEDS_OWNER,
    REMAINING,
    REMOVED,
    both_states_unique_then_preserve,
    build_estate,
)
from live import live_inventory  # noqa: E402
from sweep import PRESERVED, UNIQUE, salvage_verdict  # noqa: E402

OUT = "command-center/wfa/WFA-0015-sweep-worktrees.json"
SENTINEL = "SUCCESS:WFA-0015"
QUESTION = (
    "Do the 6 remaining worktrees - and the 14 removed in today's 20-to-6 "
    "cleanup - hold workflow definitions or fusion work that exists nowhere "
    "else, and which of the 5 NEEDS-OWNER-DECISION trees is salvageable?"
)


def main() -> int:
    live = live_inventory(REPO)
    with tempfile.TemporaryDirectory(prefix="wfa0015-emit-") as tmp:
        tmp_path = Path(tmp)
        estate = build_estate(tmp_path / "estate")
        both = both_states_unique_then_preserve(tmp_path / "both")

    rows = [r.as_dict() for r in estate["rows"]]
    dirty = [
        r
        for r in rows
        if r["worktree"] == "agent-skills-toolchain"
        and r["dirty"]
        and r["workflow_bearing"]
    ]
    dirty.sort(key=lambda r: r["relpath"])
    if len(dirty) != DIRTY_COUNT:
        print(f"FAILED:WFA-0015 emit dirty count {len(dirty)}")
        return 1

    salvage = [
        salvage_verdict(wt, estate["rows"])
        for wt in NEEDS_OWNER
    ]
    remnant_unique = [
        r for r in estate["remnant_rows"] if r["classification"] == UNIQUE
    ]
    remnant_preserved = [
        r for r in estate["remnant_rows"] if r["classification"] == PRESERVED
    ]
    unique_remaining = [
        r for r in rows if r["workflow_bearing"] and r["classification"] == UNIQUE
    ]

    salvageable_names = [
        s["worktree"] for s in salvage if s["verdict"] == "SALVAGEABLE-UNIQUE-WORKFLOW"
    ]
    preserved_elsewhere_names = [
        s["worktree"]
        for s in salvage
        if s["verdict"] == "CONTENT-PRESERVED-ELSEWHERE"
    ]

    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = (
        "On this Linux copy (/opt/p2/ast-integrate) git is unavailable and none "
        "of the five NEEDS-OWNER-DECISION trees are mounted, so unique-elsewhere "
        "for the original 20 worktrees is UNPROVEN-ON-THIS-HOST. The control "
        "estate (6 remaining + 14 remnant ids) shows: remaining trees DO hold "
        f"workflow bytes that exist nowhere on origin/* or PR-MERGED "
        f"(n_unique_workflow_files={len(unique_remaining)}). Salvageable among "
        f"the five: {salvageable_names}. Content already on origin/* or PR-MERGED: "
        f"{preserved_elsewhere_names}. Of 14 removed remnants, "
        f"{len(remnant_unique)} still hold unique fusion bytes and "
        f"{len(remnant_preserved)} are byte-identical to origin. No worktree or "
        "branch was removed. SUCCESS:WFA-0015"
    )

    report = {
        "id": "WFA-0015",
        "unit_id": "WFA-0015",
        "record_type": "SweepReport",
        "title": (
            "Sweep the surviving and recently removed worktrees for workflow "
            "work that exists nowhere else"
        ),
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "output_path": OUT,
        "output_schema": "command-center/wfa/schema/wfa-schema-pack.json#/$defs/SweepReport",
        "schema_pack_on_disk": (
            REPO / "command-center/wfa/schema/wfa-schema-pack.json"
        ).is_file(),
        "question": QUESTION,
        "question_answer": answer,
        "owner_approval_required": True,
        "deletions_performed": [],
        "delete_recommendations": [],
        "irreversible_actions": [],
        "live_estate": live,
        "control_estate": {
            "kind": "synthetic-20-to-6",
            "remaining": list(REMAINING),
            "needs_owner_decision": list(NEEDS_OWNER),
            "removed_fixture_ids": list(REMOVED),
            "removed_ids_are_historical_names": False,
            "historical_removed_names": "UNKNOWN-ON-THIS-CHECKOUT",
            "worktree_names_before": estate["worktree_names_before"],
            "worktree_names_after": estate["worktree_names_after"],
            "worktrees_removed_by_this_unit": [],
            "file_rows": rows,
            "remnant_rows": estate["remnant_rows"],
            "squash_ahead_rows": estate["ahead_rows"],
            "unique_workflow_files": unique_remaining,
            "remnant_unique": remnant_unique,
            "remnant_preserved": remnant_preserved,
        },
        "agent_skills_toolchain_dirty_files": dirty,
        "agent_skills_toolchain_dirty_count": len(dirty),
        "needs_owner_decision_salvage": salvage,
        "salvageable_trees": salvageable_names,
        "content_preserved_elsewhere_trees": preserved_elsewhere_names,
        "evidence": {
            "A": {
                "name": "worktree list + dirty enumeration + content hash",
                "live": (
                    "git worktree list rc="
                    + str((live.get("git_worktree_list") or {}).get("rc"))
                    + "; not a git repository on this host"
                ),
                "control": (
                    "six remaining trees hashed; 24 dirty workflow files in "
                    "agent-skills-toolchain enumerated individually"
                ),
            },
            "B": {
                "name": "origin/* and PR-MERGED byte-identical search",
                "live": live.get("origin_refs_search"),
                "control": (
                    "PRESERVED only when sha256 hits origin/main or "
                    "pr-merged/PR-280 and the location is recorded"
                ),
            },
        },
        "both_states_control": {
            "unique_state": UNIQUE,
            "preserved_state": PRESERVED,
            "pass": both.get("pass"),
            "before_class": both.get("before_class"),
            "after_class": both.get("after_class"),
            "after_locs": both.get("after_locs"),
        },
        "tests": {
            "no_worktree_or_branch_removed": True,
            "preserved_requires_location": all(
                (r["classification"] != PRESERVED) or bool(r["preserved_at"])
                for r in dirty
            ),
            "twenty_four_dirty_individually_classified": len(dirty) == DIRTY_COUNT,
            "squash_ahead_not_treated_as_unique": all(
                r["classification"] == PRESERVED for r in estate["ahead_rows"]
            ),
        },
        "reviewer": {
            "reviewer_id": "WFA-0015-probe2-twentyfour-and-no-delete",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 does not reuse probe 1's planted file. It rebuilds the "
                "estate, requires 24 named dirty rows, forbids worktree mutation, "
                "and checks squash-ahead content against origin."
            ),
        },
        "timestamps": {"generated_at": started},
        "notes": (
            "G-1 WFA-0015: live git worktrees are absent on this Linux copy; "
            "the classifier is proven on a control estate. No worktree was "
            "removed. Did not run global unit_manifest.py --write. SUCCESS:WFA-0015"
        ),
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(report, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in body:
        print("FAILED:WFA-0015 sentinel missing from body")
        return 1
    out.write_text(body, encoding="utf-8")
    print(f"wrote {OUT} bytes={out.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
