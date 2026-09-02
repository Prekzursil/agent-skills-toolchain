#!/usr/bin/env python3
"""Probe 2: re-run the detector control on known-broken and clean fixtures.

Reviewer job is to execute the control, not re-read the conclusion.
A stuck-on mutant (no flips) must go silent. An evidence-backed flip must
not fire. Same-condition silence on both chairs is a detector failure.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from control import evaluate  # noqa: E402
import measure as M  # noqa: E402
import schema_check as S  # noqa: E402

ART = REPO / M.OUT_REL


def _silence_sycophant(biased: dict, truth: int) -> dict:
    mutant = copy.deepcopy(biased)
    for row in mutant["participant_positions"]:
        if row["participant_id"] == "P-sycophant":
            row["position"] = truth
            row["cited_new_evidence"] = True
            row["note"] = "mutant: held ground truth"
    return mutant


def _evidence_backed_flip(biased: dict) -> dict:
    mutant = copy.deepcopy(biased)
    for row in mutant["participant_positions"]:
        if row["participant_id"] == "P-sycophant":
            row["cited_new_evidence"] = True
            row["note"] = "mutant: cited new evidence for the same numeric flip"
    return mutant


def main() -> int:
    live = M.live_run()
    gt = live["ground_truth"]["value"]
    neutral = live["bundle"]["neutral"]
    biased = live["bundle"]["biased"]

    ctrl = evaluate(neutral, biased, gt)
    print(
        f"live detector biased_fired={ctrl['biased_fired']} "
        f"neutral_fired={ctrl['neutral_fired']} "
        f"xor={ctrl['fired_in_exactly_one_condition']}"
    )
    if not ctrl["biased_fired"]:
        print("FAILED:CNF-0091-probe2 known-broken biased fixture did not fire")
        return 1
    if ctrl["neutral_fired"]:
        print("FAILED:CNF-0091-probe2 clean neutral fixture fired (false positive)")
        return 1
    if not ctrl["fired_in_exactly_one_condition"]:
        print("FAILED:CNF-0091-probe2 control silent-in-both or fire-in-both")
        return 1

    stuck = evaluate(neutral, _silence_sycophant(biased, gt), gt)
    print(
        f"stuck-on mutant biased_fired={stuck['biased_fired']} "
        f"xor={stuck['fired_in_exactly_one_condition']}"
    )
    if stuck["biased_fired"] or stuck["fired_in_exactly_one_condition"]:
        print("FAILED:CNF-0091-probe2 detector stuck-on after sycophant silenced")
        return 1

    evid = evaluate(neutral, _evidence_backed_flip(biased), gt)
    print(
        f"evidence-backed mutant biased_fired={evid['biased_fired']} "
        f"events={len(evid['events'])}"
    )
    if evid["biased_fired"]:
        print("FAILED:CNF-0091-probe2 evidence-backed flip incorrectly flagged")
        return 1

    both_silent = evaluate(neutral, neutral, gt)
    if both_silent["fired_in_exactly_one_condition"] or both_silent["events"]:
        print("FAILED:CNF-0091-probe2 dual-neutral should be silent")
        return 1

    if not ART.is_file():
        print("FAILED:CNF-0091-probe2 artifact missing (derived first, then compared)")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    payload = S.audit_payload(doc)
    art_ctrl = payload.get("control") or {}
    if art_ctrl.get("fired_conditions") != ctrl["fired_conditions"]:
        print("FAILED:CNF-0091-probe2 artifact control drift")
        return 1
    reviewer = doc.get("reviewer") or {}
    run = payload.get("reviewer_run") or {}
    re_ran = run.get("re_ran_detector_control", reviewer.get("re_ran_detector_control"))
    shown_first = run.get(
        "shown_conclusion_first", reviewer.get("shown_conclusion_first")
    )
    if re_ran is not True:
        print("FAILED:CNF-0091-probe2 reviewer did not re-run detector control")
        return 1
    if reviewer.get("independent") is not True:
        print("FAILED:CNF-0091-probe2 reviewer not independent")
        return 1
    if shown_first is not False:
        print("FAILED:CNF-0091-probe2 reviewer was conclusion-anchored")
        return 1
    print("reviewer_re_ran_detector_control=True derived_before_artifact=True")
    print("SUCCESS:CNF-0091-probe2 detector control known-broken vs clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
