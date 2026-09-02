#!/usr/bin/env python3
"""IMP-0255 probe 2: updated benchmark catches the original failure on re-run.

Independent of validate_change's KEEP decision: after a measured KEEP the
frozen benchmark must include the new case. Scoring the pre-change solver
against that updated bench (via independent_score, not the keeper) must
fail; scoring the kept solver must pass. A second re-run must agree.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from workflow_foundry.self_improvement import (  # noqa: E402
    KEEP,
    IMPROVED_SOLVER,
    SOLVER_PATH,
    demo_fixtures,
    independent_score,
    validate_change,
)


def main() -> int:
    tree, frozen, extra = demo_fixtures()
    pre_tree, _, _ = demo_fixtures()
    archive = Path("/tmp/imp-0255-probe2-archive")
    archive.mkdir(parents=True, exist_ok=True)

    # Frozen bench before KEEP must NOT already catch the hyphen regression.
    pre_update_old = independent_score(pre_tree, frozen)
    keep = validate_change(
        tree,
        {SOLVER_PATH: IMPROVED_SOLVER},
        frozen,
        extra,
        archive_dir=archive,
        change_id="improve",
    )

    run1_old = independent_score(pre_tree, frozen)
    run1_new = independent_score(tree, frozen)
    run2_old = independent_score(pre_tree, frozen)
    run2_new = independent_score(tree, frozen)

    catches_regression = (
        pre_update_old.passed == pre_update_old.total
        and keep.decision == KEEP
        and "hyphen" in keep.promoted_case_ids
        and run1_old.passed < run1_old.total
        and run1_new.passed == run1_new.total
        and run2_old.passed == run1_old.passed
        and run2_new.passed == run1_new.passed
        and any(r.id == "hyphen" and not r.passed for r in run1_old.rows)
        and any(r.id == "hyphen" and r.passed for r in run1_new.rows)
    )
    payload = {
        "probe": "probe2-benchmark-updated",
        "unit_id": "IMP-0255",
        "keep_decision": keep.decision,
        "promoted_case_ids": keep.promoted_case_ids,
        "frozen_case_ids": [c.id for c in frozen.cases],
        "pre_update_old_passed": pre_update_old.passed,
        "pre_update_old_total": pre_update_old.total,
        "run1_old": run1_old.to_dict(),
        "run1_new": run1_new.to_dict(),
        "run2_old_passed": run2_old.passed,
        "run2_new_passed": run2_new.passed,
        "independent_scorer": "independent_score",
        "keeper_not_used_for_grade": True,
        "catches_regression": catches_regression,
        "pass": bool(catches_regression),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:IMP-0255-probe2 updated benchmark does not catch regression")
        return 1
    print(
        "SUCCESS:IMP-0255-probe2 updated benchmark fails on pre-change solver "
        "and passes on kept solver (re-run agrees)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
