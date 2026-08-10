#!/usr/bin/env python
"""MY OWN CONTROL WAS MIS-SPECIFIED. Recording the correction rather than deleting it.

`wave4_abstain_probe.py` asserted that at `floor=0.0` the router must fire on EVERY
negative (`abstain_rate == 0.0`). It measured 0.0556 (2 of 36 still abstained), so my own
both-states control reported `sweep_is_really_applying_the_floor: false` - a
self-contradicting output, which is a DETECTOR failure and not a finding about the router.

The expectation was wrong. Selection is an AND-gate: the effective cut is
`max(SCORE_FLOOR, mu + Z*sd)` (`router.py:431`). Driving the floor to 0 leaves the ADAPTIVE
arm binding, so a query where nothing clears `mu + 4*sd` abstains at ANY floor. The
corrected criterion is monotone separation, not saturation:

    abstain(floor=0.0) < abstain(default) < abstain(floor=1.0) == 1.0

This script re-measures with the corrected criterion AND proves the mechanism by reporting
the `binding` arm for the queries that still abstain at floor=0.0 - if the override were
inert those would be bound by 'floor', and they are not.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent / "platform"
TARGET = HERE / "WAVE4-ABSTAIN-PROBE.json"
sys.path.insert(0, str(BUILD))

from routing import index as ridx  # noqa: E402
from routing.router import Router  # noqa: E402

import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location("w4ab", HERE / "wave4_abstain_probe.py")
ab = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
spec.loader.exec_module(ab)  # type: ignore[union-attr]

router = Router.build(ridx.discover())
negatives = ab.LANE_NEGATIVES + ab.MY_NEGATIVES


def run(floor: float | None) -> tuple[int, list[dict]]:
    quiet = []
    for t in negatives:
        d = router.route(t, k=5, floor=floor)
        if not d.fits:
            quiet.append(
                {
                    "query": t,
                    "binding": d.threshold_stats.get("binding"),
                    "floor_arm": d.threshold_stats.get("floor"),
                    "adaptive_arm": d.threshold_stats.get("adaptive"),
                    "best_score": (d.fallback or {}).get("best_score"),
                }
            )
    return len(quiet), quiet


a0, q0 = run(0.0)
ad, _ = run(None)
a1, _ = run(1.0)
n = len(negatives)

corrected = {
    "MY_ORIGINAL_CONTROL_WAS_WRONG": (
        "it asserted abstain_rate == 0.0 at floor=0.0; measured 0.0556. The assertion, not "
        "the sweep, was the defect: selection is max(floor, mu+Z*sd), so the ADAPTIVE arm "
        "still binds when the floor is driven to 0 (router.py:431)."
    ),
    "corrected_criterion": "abstain(0.0) < abstain(default) < abstain(1.0) == 1.0",
    "abstain_at_floor_0.0": round(a0 / n, 4),
    "abstain_at_default_floor": round(ad / n, 4),
    "abstain_at_floor_1.0": round(a1 / n, 4),
    "monotone_and_separating": a0 < ad < a1 and a1 == n,
    "floor_override_is_LIVE": a0 < ad,
    "the_2_that_still_abstain_at_floor_0": q0,
    "all_residual_abstainers_bound_by_adaptive_not_floor": all(
        r["binding"] == "adaptive" for r in q0
    ),
    "n_negatives": n,
}

doc = json.loads(TARGET.read_text(encoding="utf-8"))
doc["both_states_control_CORRECTED"] = corrected
TARGET.write_text(json.dumps(doc, indent=2), encoding="utf-8")
print(json.dumps(corrected, indent=2))
print("SUCCESS:wave4-control-fix")
