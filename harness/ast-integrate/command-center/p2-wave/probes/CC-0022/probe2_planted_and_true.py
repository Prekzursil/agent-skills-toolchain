#!/usr/bin/env python3
"""Probe 2: planted stale entry fires (not hardcoded to line 175); currently-true does not.

Also the independent meaning review: only namespace/tense/supersession metadata
changed; original collision wording is preserved under superseded_by.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center" / "lib"))
sys.path.insert(0, str(HERE))

import build_fixtures  # noqa: E402
from decision_log_reconcile import ORIGINAL_SENTENCE, unchanged_except_collision  # noqa: E402
from decision_log_sentinel import scan  # noqa: E402
from option_id_collision_probe import live_snapshot  # noqa: E402

AFTER = HERE / "fixtures" / "decision-log-after.md"
BEFORE = HERE / "fixtures" / "decision-log-before.md"
LIVE = REPO / "17-DECISION-LOG.md"
OPT = REPO / "command-center/option-id/07-OPTION-UNIVERSE.family-M-slice.md"
POST = REPO / "command-center/option-id/13-ARCHITECTURE-CANDIDATES.post-fix-slice.md"

PLANT_STALE = """
## DL-PLANT-STALE Planted stale collision claim
date: 2026-08-24
status: CURRENT
valid_as_of: 2026-08-24

The 31-way option-id collision between 07-OPTION-UNIVERSE family M and 13-ARCHITECTURE-CANDIDATES is live. Status: Queued as P2-09.
"""

PLANT_TRUE = """
## DL-PLANT-TRUE Architecture prefix after fb02
date: 2026-08-24
status: CURRENT
valid_as_of: 2026-08-24

13-ARCHITECTURE-CANDIDATES uses the MECH-NN prefix after the 2026-08-07 18:41 re-prefix.
probe-assert: collision_count == 0
"""


def main() -> int:
    rc = build_fixtures.main()
    if rc != 0:
        print("FAILED:CC-0022-probe2 fixture build")
        return 1
    snap = live_snapshot(repo=REPO, option_path=OPT, arch_path=POST)
    after = AFTER.read_text(encoding="utf-8")
    before = BEFORE.read_text(encoding="utf-8")

    review = unchanged_except_collision(before, after)
    print("meaning_review=" + str(review))
    if not review.get("ok"):
        print("FAILED:CC-0022-probe2 reconcile changed more than namespace/tense/supersession")
        return 1
    if ORIGINAL_SENTENCE not in after:
        print("FAILED:CC-0022-probe2 superseded wording was deleted")
        return 1
    live = LIVE.read_text(encoding="utf-8")
    if live != after:
        print("FAILED:CC-0022-probe2 live 17-DECISION-LOG.md is not the reconciled log")
        return 1

    planted = after + PLANT_STALE
    rp = scan(planted, snapshot=snap, log_path="planted-stale-copy")
    plant_ids = [f.entry_id for f in rp.fires]
    print(f"planted_fired={rp.fired} fire_ids={plant_ids}")
    if not rp.fired:
        print("FAILED:CC-0022-probe2 planted stale entry did not fire (hardcoded to line 175?)")
        return 1
    if "DL-PLANT-STALE" not in plant_ids:
        print("FAILED:CC-0022-probe2 fire list missing DL-PLANT-STALE")
        return 1
    if "DL-0001" in plant_ids:
        print("FAILED:CC-0022-probe2 currently-true DL-0001 fired")
        return 1

    true_copy = after + PLANT_TRUE
    rt = scan(true_copy, snapshot=snap, log_path="planted-true-copy")
    true_ids = [f.entry_id for f in rt.fires]
    print(f"true_copy_fired={rt.fired} fire_ids={true_ids}")
    if rt.fired:
        print("FAILED:CC-0022-probe2 currently-true planted entry fired")
        return 1

    rl = scan(live, snapshot=snap, log_path=str(LIVE))
    if rl.fired:
        print("FAILED:CC-0022-probe2 live log fired")
        return 1
    print("SUCCESS:CC-0022-probe2 planted-stale currently-true meaning-preserving")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
