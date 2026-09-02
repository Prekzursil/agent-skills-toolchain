#!/usr/bin/env python3
"""BLD-0054 probe 2: named-four uncovered list + independent reviewer novel abuse."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402
import runtime as R  # noqa: E402

NOVEL = "prior_consensus_anchoring"


def main() -> int:
    cen = C.run_census(R.SPEC_ABUSES)
    uncovered = cen["uncovered_by_named_four"]
    novel = R.run_reviewer_novel()
    novel_ok = bool(novel.get("both_states_ok")) and NOVEL not in R.SPEC_ABUSES
    named_ok = cen["named_four"]["artifacts_present"] == 0
    payload = {
        "probe": "probe2_reviewer_novel_abuse",
        "named_four_artifacts_present": cen["named_four"]["artifacts_present"],
        "named_four_catalog_mapped": cen["named_four"]["catalog_mapped_abuses"],
        "uncovered_by_named_four": uncovered,
        "production_runtime": cen["production_runtime"]["verdict"],
        "reviewer_novel_abuse": NOVEL,
        "novel_in_spec_list": NOVEL in R.SPEC_ABUSES,
        "novel_both_states_ok": novel_ok,
        "novel_control": novel.get("control"),
    }
    print(json.dumps(payload, sort_keys=True))
    if not uncovered:
        print("FAILED:BLD-0054-probe2 uncovered list empty")
        return 1
    if not novel_ok:
        print("FAILED:BLD-0054-probe2 novel abuse both-states")
        return 1
    if NOVEL in uncovered:
        print("FAILED:BLD-0054-probe2 novel abuse leaked into spec uncovered list")
        return 1
    print(
        "SUCCESS:BLD-0054-probe2 uncovered="
        + ",".join(uncovered)
        + f" named_artifacts={cen['named_four']['artifacts_present']} novel={NOVEL}"
    )
    # named_ok is informational: artifacts are expected absent on this worktree
    _ = named_ok
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
