#!/usr/bin/env python3
"""Probe 1: plant a documented-but-absent field and assert the gate finds it.

Both-states: the planted field is found on the bad fixture and absent on the
clean fixture. An uncontrolled zero is DETECTOR-FAILURE, not CLEAN.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import gate as G  # noqa: E402
import surfaces as S  # noqa: E402

ART = REPO / "command-center/phase4/conformance/ARC-0104.json"


def main() -> int:
    control = S.run_detector_control()
    planted = control["planted_field"]
    if planted != G.PLANTED_FIELD:
        print("FAILED:ARC-0104-probe1 planted field name drift")
        return 1
    if not control["fired"]:
        print("FAILED:ARC-0104-probe1 detector control did not fire")
        print(json.dumps(control, indent=2, default=str)[:3000])
        return 1
    if set(control["found_in"]) != {"docs_not_schema", "docs_not_impl"}:
        print("FAILED:ARC-0104-probe1 planted field not in both absent directions")
        print(control["found_in"])
        return 1
    if not control["clean_silent"]:
        print("FAILED:ARC-0104-probe1 clean fixture was not silent")
        return 1
    if control["default_mismatch_control_count"] < 1:
        print("FAILED:ARC-0104-probe1 default-mismatch fixture produced zero")
        return 1
    if control["uncontrolled_zero_verdict"] != "DETECTOR-FAILURE":
        print("FAILED:ARC-0104-probe1 uncontrolled zero was not DETECTOR-FAILURE")
        return 1

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        recorded = G.artifact_section(doc, "detector_control") or {}
        if not isinstance(recorded, dict):
            print("FAILED:ARC-0104-probe1 artifact detector_control missing")
            return 1
        if recorded.get("planted_field") != planted:
            print("FAILED:ARC-0104-probe1 artifact planted_field drift")
            return 1
        if not recorded.get("clean_silent"):
            print("FAILED:ARC-0104-probe1 artifact clean_silent false")
            return 1
        if planted not in json.dumps(recorded):
            print("FAILED:ARC-0104-probe1 artifact omitted planted field")
            return 1

    out = {
        "probe": "probe1-detector-control",
        "unit_id": "ARC-0104",
        "planted_field": planted,
        "found_in": control["found_in"],
        "clean_silent": True,
        "uncontrolled_zero": "DETECTOR-FAILURE",
        "fired": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:ARC-0104-probe1 planted documented-but-absent field detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
