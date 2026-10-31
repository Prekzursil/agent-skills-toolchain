#!/usr/bin/env python3
"""Probe 2: known-broken fixture must fail; known-good must pass.

Both-states: a checker silent on the broken fixture and the good fixture
measures nothing. A scorer that reads call_sheet_grade would green the
grade-leak mutant.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import call_sheet as CS  # noqa: E402
import score as S  # noqa: E402

ART = REPO / "command-center/research/RES-0108.json"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0108-probe2 {msg}")
    return 1


def main() -> int:
    doc = json.loads(ART.read_text(encoding="utf-8"))
    ctrl = doc.get("detector_control") or {}

    good = CS.known_good()
    broken = CS.known_broken()
    leak = CS.grade_leak_mutant()
    zeros = {
        "id": "CTRL-ZERO",
        "call_sheet_grade": "TIER-1",
        "features": {
            "leverage": 0,
            "integration_cost": 0,
            "irreplaceable": False,
            "rename_of_existing": False,
            "evidence_tier": "E4",
            "has_baseline": False,
            "has_effect_size": False,
            "bus_fit": "SECOND RUNTIME",
        },
    }

    g = S.apply(good)
    b = S.apply(broken)
    g2 = S.apply_independent(good)
    b2 = S.apply_independent(broken)
    lk = S.apply(leak)
    z = S.apply(zeros)

    print(f"known_good gem={g['gem']} indep={g2['gem']} reasons={g['reasons']}")
    print(f"known_broken gem={b['gem']} indep={b2['gem']} reasons={b['reasons']}")
    print(f"grade_leak gem={lk['gem']} grade={leak.get('call_sheet_grade')}")
    print(f"all_zero gem={z['gem']}")

    if g["gem"] is not True or g2["gem"] is not True:
        return fail("silent-on-good")
    if b["gem"] is not False or b2["gem"] is not False:
        return fail("silent-on-broken")
    if lk["gem"] is not False:
        return fail("grade-leak-false-green")
    if z["gem"] is True:
        return fail("zero-features-scored-gem")
    if g["gem"] == b["gem"]:
        return fail("silent-in-both-states")

    # Repair mutant: drop second-runtime / E4 / replaceable / high cost.
    repaired = copy.deepcopy(broken)
    repaired["features"] = dict(CS.known_good()["features"])
    r = S.apply(repaired)
    print(f"repaired gem={r['gem']}")
    if r["gem"] is not True:
        return fail("repaired-broken-still-fails")

    rec_good = ctrl.get("known_good_gem")
    rec_bad = ctrl.get("known_broken_gem")
    if rec_good is not True or rec_bad is not False:
        return fail(f"artifact-control-drift good={rec_good} broken={rec_bad}")

    print("fired_on_broken=True silent_on_good=True grade_leak_blocked=True")
    print("SUCCESS:RES-0108-probe2 known-broken fixture fails as required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
