#!/usr/bin/env python3
"""Probe 1: counting-rule invariance across two designs plus duplicate-id plant."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import inventory as I  # noqa: E402

COST = REPO / "command-center/phase3/A9/COST.json"
DESIGNS = ("A1", "A9")
BAND = 1


def main() -> int:
    cost = json.loads(COST.read_text(encoding="utf-8"))
    by_id = {d["architecture_id"]: d for d in cost.get("designs") or []}
    fail = False
    for arch in DESIGNS:
        fwd = I.count_ids_forward(arch)
        rev = I.count_ids_by_kind_sum(arch)
        recorded = by_id.get(arch) or {}
        rec = recorded.get("understandability_budget")
        delta = abs(fwd - rev)
        rec_ok = rec == fwd
        match = delta <= BAND and rec_ok
        if not match:
            fail = True
        print(
            f"design {arch} forward={fwd} kind_sum={rev} delta={delta} "
            f"recorded={rec} rec_ok={rec_ok} match={match}"
        )
        if recorded.get("item_ids") != I.item_ids(arch):
            fail = True
            print(f"FAILED:ARC-0060-probe1 {arch} item_ids drift")

    planted = copy.deepcopy(I.ITEMS)
    planted.append(copy.deepcopy(planted[0]))
    orig = I.count_ids_forward("A1")
    after = I.count_ids_forward("A1", planted)
    plant_ok = after == orig
    print(f"duplicate-id plant A1 orig={orig} after={after} silent={plant_ok}")
    if not plant_ok:
        fail = True
        print("FAILED:ARC-0060-probe1 duplicate id incremented the count")

    # Live DESIGN cross-check is informational: A1 dossier role count must
    # be recorded honestly (present + integer) and must NOT be used as the
    # A1 headline (different granularity).
    a1_live = (by_id.get("A1") or {}).get("live_design_file_set") or {}
    if a1_live.get("dossier_present") is True:
        roles = a1_live.get("unique_roles")
        headline = (by_id.get("A1") or {}).get("understandability_budget")
        print(f"live A1 file_set roles={roles} headline={headline}")
        if not isinstance(roles, int) or roles < 1:
            fail = True
            print("FAILED:ARC-0060-probe1 A1 live role count missing")
        if roles == headline:
            print(
                "NOTE: live role count equals headline; still ok if inventories coincide"
            )

    if fail:
        print("FAILED:ARC-0060-probe1 counting-rule invariance")
        return 1
    print("SUCCESS:ARC-0060-probe1 counting-rule invariance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
