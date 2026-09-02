#!/usr/bin/env python3
"""Probe 2: independent silent-fallback detector + overclaim + live anchors.

The planted mutant (consumer --mode silent) must be classified silent-degradation.
The loud consumer must not. Dropping artifact_marked_degraded from a
degraded-artifact row must make the overclaim checker reject the report.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import anchors as A
import harness as H
import inventory as I
import overclaim as O

HERE = Path(__file__).resolve().parent
REPO = I.REPO
ART = REPO / I.OUT_REL


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNF-0117-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    ok, why = O.check(doc)
    print(f"overclaim_ok={ok} {why}")
    if not ok:
        print("FAILED:CNF-0117-probe2 overclaim failed on artifact")
        return 1

    mutant = copy.deepcopy(doc)
    stripped = False
    denial_rows = O.denials_of(mutant)
    for row in denial_rows:
        if row.get("classification") == "degraded-artifact":
            row["artifact_marked_degraded"] = False
            stripped = True
            break
    if not stripped:
        print("FAILED:CNF-0117-probe2 no degraded-artifact row to strip")
        return 1
    mok, mwhy = O.check(mutant)
    print(f"mutant_ok={mok} {mwhy}")
    if mok:
        print("FAILED:CNF-0117-probe2 unmarked degraded-artifact was accepted")
        return 1

    live = H.measure(include_mutant=True)
    probe = live["silent_degradation_probe"]
    print(
        f"mutant_silent={probe['fired_on_bad_state']} "
        f"good_not_silent={probe['silent_on_good_state']}"
    )
    if probe["fired_on_bad_state"] is not True:
        print("FAILED:CNF-0117-probe2 silent mutant was not classified silent-degradation")
        return 1
    if probe["silent_on_good_state"] is not True:
        print("FAILED:CNF-0117-probe2 good consumer classified as silent-degradation")
        return 1
    rec = O.payload(doc).get("silent_degradation_probe") or {}
    if rec.get("fired_on_bad_state") is not True or rec.get("silent_on_good_state") is not True:
        print("FAILED:CNF-0117-probe2 artifact detector flags false")
        return 1

    plan = A.evidence_plan()
    if len(plan) < 4:
        print("FAILED:CNF-0117-probe2 evidence plan short")
        return 1
    for i, row in enumerate(plan):
        rok, rwhy = A.resolve(REPO, row["path"], row["line"], row["snippet"])
        print(f"anchor[{i}] ok={rok} {rwhy}")
        if not rok:
            print("FAILED:CNF-0117-probe2 unresolved anchor")
            return 1
    recorded = {(e.get("anchor"), e.get("claim")) for e in (doc.get("evidence") or [])}
    for row in plan:
        if (row["anchor"], row["claim"]) not in recorded:
            print(f"FAILED:CNF-0117-probe2 evidence missing {row['anchor']}")
            return 1

    if I.TOKEN_VALUE in ART.read_text(encoding="utf-8"):
        print("FAILED:CNF-0117-probe2 fixture token leaked")
        return 1
    print("SUCCESS:CNF-0117-probe2 silent-mutant detector anchors reviewer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
