#!/usr/bin/env python3
"""probe1 for TST-0014: the enumerator's own known-present control fires.

Detector-on-detector control: the planted fixtures (PLANTED-VALIDATOR,
PLANTED-HOOK, PLANTED-GATE) MUST be found before any absence/census number is
trusted. Also re-counts the live census with the control registry.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UID = "TST-0014"


def load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    checks = {}
    en = load("dc_enumerate", "tools/detector_control/enumerate.py")
    ct = load("dc_controls", "tools/detector_control/controls.py")
    control = en.enumerator_control(None)
    checks["known_present_fired"] = control["fired"] is True
    checks["fired_before_absence"] = control["fired_before_absence_reported"] is True
    checks["all_planted_found"] = control["missing_planted"] == []
    detectors = en.enumerate_detectors(REPO)
    reg = ct.load_registry()
    counts = ct.census(detectors, reg)
    checks["census_live"] = counts["detector_count"] > 0
    checks["registry_covers_all_live"] = counts["uncontrolled_count"] == 0
    ok = all(bool(v) for v in checks.values())
    print(json.dumps({"unit_id": UID, "probe": "probe1-enumerator-known-present", "pass": ok,
                      "control": control, "census": counts, "checks": checks}))
    if ok:
        print(f"SUCCESS:{UID}-probe1 planted control fired first ({len(control['found_planted'])}/3); live census {counts['detector_count']} detectors, {counts['controlled_count']} controlled, {counts['uncontrolled_count']} uncontrolled")
        return 0
    print(f"FAILED:{UID}-probe1 " + ",".join(k for k, v in checks.items() if not v))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
