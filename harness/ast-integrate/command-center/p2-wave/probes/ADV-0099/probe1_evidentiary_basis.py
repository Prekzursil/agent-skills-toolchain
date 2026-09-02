#!/usr/bin/env python3
"""Probe 1: evidentiary basis of every expertise / vote-weight input."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import audit as A  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0099-hallucinated-expertise-in-selection.json"
UID = "ADV-0099"


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0099-probe1 {msg}")
    return 1


def main() -> int:
    live = A.run_audit()
    slim = {
        "probe": "probe1-evidentiary-basis",
        "unit_id": UID,
        "pathology_confirmed": live["pathology_confirmed"],
        "checkable_inputs": live["checkable_inputs"],
        "unverifiable_inputs": live["unverifiable_inputs"],
        "inputs": [
            {
                "id": i["id"],
                "path": i["path"],
                "present": i["present"],
                "evidentiary_basis": i["evidentiary_basis"],
                "used_as": i.get("used_as"),
            }
            for i in live["inputs"]
        ],
        "bld0054_accepts_unmeasured_high_score": next(
            i["accepts_unmeasured_high_score"]
            for i in live["inputs"]
            if i["id"] == "bld0054-competence-probe"
        ),
        "weights_mentions_expertise_or_calibration": next(
            i["mentions_expertise_or_calibration"]
            for i in live["inputs"]
            if i["id"] == "production-vote-weights"
        ),
        "select_expertise_present": next(
            i["present"]
            for i in live["inputs"]
            if i["id"] == "production-select-expertise"
        ),
        "pass": live["pass"] and live["pathology_confirmed"],
    }
    print(json.dumps(slim, indent=2, sort_keys=True))
    if not live["pass"]:
        return fail("audit engine failed")
    if live["checkable_inputs"]:
        return fail(f"unexpected checkable inputs {live['checkable_inputs']}")
    if not live["pathology_confirmed"]:
        return fail("pathology not confirmed on live inputs")
    if slim["select_expertise_present"]:
        return fail("select_expertise.py present; this probe expected absence")
    if slim["weights_mentions_expertise_or_calibration"]:
        return fail("weights.py unexpectedly mentions expertise/calibration")
    if not slim["bld0054_accepts_unmeasured_high_score"]:
        return fail("BLD-0054 refused a caller-supplied quiz_accuracy=1.0")
    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        recorded = (doc.get("probe1") or {}).get("pathology_confirmed")
        if recorded is not True:
            return fail("artifact probe1.pathology_confirmed is not true")
        verdicts = [t.get("verdict") for t in (doc.get("targets") or [])]
        if "CONFIRMED" not in verdicts:
            return fail("artifact missing CONFIRMED target")
    print("SUCCESS:ADV-0099-probe1 evidentiary-basis audit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
