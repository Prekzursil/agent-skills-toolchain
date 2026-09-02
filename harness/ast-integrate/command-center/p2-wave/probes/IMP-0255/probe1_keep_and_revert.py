#!/usr/bin/env python3
"""IMP-0255 probe 1: both KEEP and REVERT branches; four blueprints register."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from workflow_foundry.blueprint_contract import omission_table  # noqa: E402
from workflow_foundry.meta_blueprints import (  # noqa: E402
    BLUEPRINT_IDS,
    all_blueprints,
    registry_snapshot,
)
from workflow_foundry.self_improvement import (  # noqa: E402
    KEEP,
    REVERT,
    HARMFUL_SOLVER,
    IMPROVED_SOLVER,
    NEUTRAL_SOLVER,
    SOLVER_PATH,
    demo_fixtures,
    validate_change,
)


def main() -> int:
    registered = all_blueprints()
    ids = [bp.id for bp in registered]
    snap = registry_snapshot()
    smokes_ok = all(row.get("ok") for row in snap["smokes"].values())
    omissions_ok = all(
        ctl["all_distinct"] and len(ctl["rows"]) == 6
        for ctl in snap["omission_controls"].values()
    )

    tree, frozen, extra = demo_fixtures()
    before = tree.digest()
    archive = Path("/tmp/imp-0255-probe1-archive")
    archive.mkdir(parents=True, exist_ok=True)

    harmful = validate_change(
        tree,
        {SOLVER_PATH: HARMFUL_SOLVER},
        frozen,
        extra,
        archive_dir=archive,
        change_id="harmful",
    )
    after_harmful = tree.digest()
    neutral = validate_change(
        tree,
        {SOLVER_PATH: NEUTRAL_SOLVER},
        frozen,
        extra,
        archive_dir=archive,
        change_id="neutral",
    )
    after_neutral = tree.digest()
    keep = validate_change(
        tree,
        {SOLVER_PATH: IMPROVED_SOLVER},
        frozen,
        extra,
        archive_dir=archive,
        change_id="improve",
    )

    both_branches = (
        harmful.decision == REVERT
        and harmful.reason == "HARMFUL"
        and harmful.revert_observed
        and after_harmful == before
        and neutral.decision == REVERT
        and neutral.reason == "NEUTRAL"
        and neutral.revert_observed
        and after_neutral == before
        and keep.decision == KEEP
        and keep.archived
        and keep.archive_path is not None
        and Path(keep.archive_path).is_file()
        and "hyphen" in keep.promoted_case_ids
        and tree.digest() != before
    )
    sample = registered[0]
    omit_rows = omission_table(sample)
    omit_ok = all(r["distinct_hit"] for r in omit_rows) and len({r["expected"] for r in omit_rows}) == 6

    payload = {
        "probe": "probe1-keep-and-revert",
        "unit_id": "IMP-0255",
        "registered_ids": ids,
        "expected_ids": list(BLUEPRINT_IDS),
        "ids_match": ids == list(BLUEPRINT_IDS),
        "smokes_ok": smokes_ok,
        "omission_controls_ok": omissions_ok and omit_ok,
        "harmful": harmful.to_dict(),
        "neutral": neutral.to_dict(),
        "keep": keep.to_dict(),
        "before_digest": before,
        "after_harmful_digest": after_harmful,
        "after_neutral_digest": after_neutral,
        "after_keep_digest": tree.digest(),
        "revert_observed_in_tree": after_neutral == before and after_harmful == before,
        "both_branches": both_branches,
        "pass": bool(
            ids == list(BLUEPRINT_IDS)
            and smokes_ok
            and omissions_ok
            and omit_ok
            and both_branches
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:IMP-0255-probe1 keep/revert or blueprint contract")
        return 1
    print(
        "SUCCESS:IMP-0255-probe1 four blueprints registered; "
        "neutral/harmful reverted (digest match); measured improvement kept"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
