#!/usr/bin/env python3
"""Probe 1: both-states control for the benchmark-gaming detector.

Overfit workflow (memorizes visible labels) is flagged; honest workflow
(true generating rule) is not. Both gaps are reported as numbers.
Partition membership is recomputed independently from the case hash.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIB = REPO / "command-center" / "lib"
sys.path.insert(0, str(LIB))

from overfit_detector.corpus import build_corpus  # noqa: E402
from overfit_detector.detector import detect  # noqa: E402
from overfit_detector.partition import (  # noqa: E402
    assert_no_heldout_touch,
    independent_slice,
    slice_of,
    split,
)
from overfit_detector.workflows import MemorizeVisibleWorkflow, TrueRuleWorkflow  # noqa: E402

RAW = HERE / "probe1-both-states.raw.json"


def main() -> int:
    cases = build_corpus(80)
    visible, heldout = split(cases)
    for case in cases:
        if independent_slice(case.id) != slice_of(case.id):
            print("FAILED:IMP-0206-probe1 partition not a pure function of case hash")
            return 1
    if independent_slice(cases[0].id) != independent_slice(cases[0].id):
        print("FAILED:IMP-0206-probe1 partition not reproducible")
        return 1

    overfit = MemorizeVisibleWorkflow(visible)
    assert_no_heldout_touch(overfit.trained_ids, [c.id for c in heldout])
    honest = TrueRuleWorkflow()

    over_r = detect(overfit, cases)
    hon_r = detect(honest, cases)
    if not over_r["flagged"] or over_r["refuter_lane"] != "benchmark-gaming":
        print("FAILED:IMP-0206-probe1 overfit not flagged", json.dumps(over_r))
        return 1
    if hon_r["flagged"] or hon_r["refuter_lane"] is not None:
        print("FAILED:IMP-0206-probe1 honest false-positive", json.dumps(hon_r))
        return 1
    if over_r["gap"] is None or hon_r["gap"] is None:
        print("FAILED:IMP-0206-probe1 gaps not numeric")
        return 1
    if not (over_r["gap"] > float(over_r["threshold"]["gap_abs"])):
        print("FAILED:IMP-0206-probe1 overfit gap not beyond threshold")
        return 1
    if not (hon_r["gap"] <= float(hon_r["threshold"]["gap_abs"])):
        print("FAILED:IMP-0206-probe1 honest gap beyond threshold")
        return 1
    if hon_r["visible_accuracy"] != 1.0 or hon_r["heldout_accuracy"] != 1.0:
        print("FAILED:IMP-0206-probe1 honest not exact on both slices", hon_r)
        return 1
    if over_r["visible_accuracy"] != 1.0 or over_r["heldout_accuracy"] != 0.0:
        print("FAILED:IMP-0206-probe1 overfit not 1.0/0.0", over_r)
        return 1

    doc = {
        "both_states": True,
        "heldout_n": over_r["heldout_n"],
        "honest_flagged": False,
        "honest_gap": hon_r["gap"],
        "honest_heldout_accuracy": hon_r["heldout_accuracy"],
        "honest_visible_accuracy": hon_r["visible_accuracy"],
        "overfit_flagged": True,
        "overfit_gap": over_r["gap"],
        "overfit_heldout_accuracy": over_r["heldout_accuracy"],
        "overfit_visible_accuracy": over_r["visible_accuracy"],
        "pass": True,
        "refuter_lane": "benchmark-gaming",
        "threshold_gap_abs": over_r["threshold"]["gap_abs"],
        "threshold_id": over_r["threshold"]["id"],
        "visible_n": over_r["visible_n"],
    }
    RAW.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"overfit_flagged=True overfit_gap={over_r['gap']} "
        f"honest_flagged=False honest_gap={hon_r['gap']} "
        f"threshold={over_r['threshold']['gap_abs']} lane=benchmark-gaming "
        f"visible_n={over_r['visible_n']} heldout_n={over_r['heldout_n']}"
    )
    print("SUCCESS:IMP-0206-probe1 both-states overfit flagged honest silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
