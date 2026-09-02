#!/usr/bin/env python3
"""Probe 2: reviewer re-runs the detector control on known-broken fixtures.

A reviewer who only re-reads the artifact has verified nothing. This probe
re-classifies the planted unlabelled receipt, the absent directory, and the
unrunnable gate, then proves two mutants (absent-as-zero, unrunnable-as-pass)
are rejected by the same checker.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import checker as K  # noqa: E402
import classify as C  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0120-not-checked-integrity.json"


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNF-0120-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    ok, why = K.check_artifact(doc)
    print(f"artifact_ok={ok} {why}")
    if not ok:
        print("FAILED:CNF-0120-probe2 checker failed on artifact")
        return 1

    audit = C.run_audit(REPO)
    live_ok = audit["controls"].get("all_passed")
    print(f"live_detector_ok={live_ok}")
    if not live_ok:
        print("FAILED:CNF-0120-probe2 live detector-control")
        print(json.dumps(audit["controls"], indent=2, sort_keys=True)[:2000])
        return 1

    planted = audit["index"]["FIXTURE-PLANTED-UNLABELLED"]
    print(
        "planted integrity={0} three_state={1}".format(
            planted.get("integrity_class"), planted.get("three_state")
        )
    )
    if planted.get("integrity_class") != "FOLDED-INTO-PASS":
        print("FAILED:CNF-0120-probe2 planted control did not fire")
        return 1

    mutant_zero = copy.deepcopy(doc)
    mutant_zero["items"] = C.naive_absent_as_zero(mutant_zero["items"])
    mok, mwhy = K.check_artifact(mutant_zero)
    print(f"mutant_absent_as_zero ok={mok} {mwhy}")
    if mok:
        print("FAILED:CNF-0120-probe2 absent-as-zero mutant was accepted")
        return 1

    mutant_gate = copy.deepcopy(doc)
    mutant_gate["items"] = C.naive_unrunnable_as_pass(mutant_gate["items"])
    gok, gwhy = K.check_artifact(mutant_gate)
    print(f"mutant_unrunnable_as_pass ok={gok} {gwhy}")
    if gok:
        print("FAILED:CNF-0120-probe2 unrunnable-as-pass mutant was accepted")
        return 1

    labelled = audit["index"]["FIXTURE-LABELLED-NOT-CHECKED"]
    if labelled.get("integrity_class") != "NOT-CHECKED":
        print("FAILED:CNF-0120-probe2 labelled control folded or missing")
        return 1
    print("labelled_not_checked integrity=NOT-CHECKED")

    evidence = doc.get("evidence") or []
    if len(evidence) < 3:
        print("FAILED:CNF-0120-probe2 evidence short")
        return 1
    for i, row in enumerate(evidence):
        rel = str(row.get("path") or "")
        snippet = str(row.get("snippet") or "")
        path = REPO / rel
        if not path.is_file():
            print(f"FAILED:CNF-0120-probe2 evidence[{i}] missing {rel}")
            return 1
        if snippet not in path.read_text(encoding="utf-8"):
            print(f"FAILED:CNF-0120-probe2 evidence[{i}] snippet not in {rel}")
            return 1
        print(f"evidence[{i}] ok {rel}")

    print("SUCCESS:CNF-0120-probe2 detector-control mutants rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
