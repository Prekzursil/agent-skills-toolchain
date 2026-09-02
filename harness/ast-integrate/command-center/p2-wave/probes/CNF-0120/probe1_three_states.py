#!/usr/bin/env python3
"""Probe 1: three-state distinction plus planted unlabelled control.

Fires on the known-broken unlabelled receipt. Silent on the labelled
NOT-CHECKED control. Refuses to treat an absent directory as nothing to check.
"""
from __future__ import annotations

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
    audit = C.run_audit(REPO)
    ctrl = audit["controls"]
    checks = [
        ("absent_dir_not_nothing_to_check", ctrl.get("absent_dir_not_nothing_to_check")),
        ("empty_not_absent_or_zero", ctrl.get("empty_not_absent_or_zero")),
        ("genuine_zero_distinct", ctrl.get("genuine_zero_distinct")),
        ("unrunnable_gate_not_silent_pass", ctrl.get("unrunnable_gate_not_silent_pass")),
        ("planted_unlabelled_caught", ctrl.get("planted_unlabelled_caught")),
        ("labelled_not_checked_not_folded", ctrl.get("labelled_not_checked_not_folded")),
        ("three_states_unmerged", ctrl.get("three_states_unmerged")),
        ("all_passed", ctrl.get("all_passed")),
    ]
    for name, ok in checks:
        print(f"{name}={ok}")
        if not ok:
            print(f"FAILED:CNF-0120-probe1 {name}")
            return 1

    idx = audit["index"]
    shapes = {
        "absent": idx["FIXTURE-ABSENT-DIR"]["three_state"],
        "empty_dir": idx["FIXTURE-EMPTY-DIR"]["three_state"],
        "empty_array": idx["FIXTURE-EMPTY-ARRAY"]["three_state"],
        "zero": idx["FIXTURE-GENUINE-ZERO"]["three_state"],
    }
    print("shapes=" + json.dumps(shapes, sort_keys=True))
    if len({shapes["absent"], shapes["empty_dir"], shapes["zero"]}) != 3:
        print("FAILED:CNF-0120-probe1 three states merged")
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0120-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    ok, why = K.check_artifact(doc)
    print(f"artifact_ok={ok} {why}")
    if not ok:
        print("FAILED:CNF-0120-probe1 artifact checker")
        return 1
    if K.SENTINEL not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNF-0120-probe1 sentinel absent")
        return 1
    live_absent = [
        r
        for r in audit["items"]
        if r.get("kind") == "confirmation" and r.get("three_state") == "ABSENT"
    ]
    if len(live_absent) < 1:
        print("FAILED:CNF-0120-probe1 confirmation inventory produced no ABSENT rows")
        return 1
    print(
        f"live_confirmation_absent={len(live_absent)} "
        f"folded={audit['summary']['folded_into_pass']} "
        f"not_checked={audit['summary']['not_checked']}"
    )
    print("SUCCESS:CNF-0120-probe1 three-states planted-unlabelled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
