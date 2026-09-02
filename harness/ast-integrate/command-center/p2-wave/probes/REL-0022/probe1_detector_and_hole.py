#!/usr/bin/env python3
"""Probe 1: detector control, then unrecorded-side-effect hole.

Must capture a known side effect before any zero-hole finding, and must
report a recovery hole when the installer writes an unrecorded file.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from canary import create, destroy  # noqa: E402
from coverage import HOLE_KEY, run_install, subtract  # noqa: E402
from inverse import recorded_keys  # noqa: E402
from observer import detector_control  # noqa: E402

ART = REPO / "command-center/receipts/REL-0022.json"


def main() -> int:
    det_home = create()
    try:
        detector = detector_control(det_home)
    finally:
        destroy(det_home)
    print(f"detector_pass={detector['pass']} produced={detector.get('produced')}")
    if not detector["pass"]:
        print("FAILED:REL-0022-probe1 detector control did not capture known side effect")
        return 1

    recorded = recorded_keys()
    hole_home = create()
    try:
        hole_obs = run_install(hole_home, extra_unrecorded=True)
        hole_sub = subtract(set(hole_obs["effect_keys"]), recorded)
        hole_fired = HOLE_KEY in hole_sub["recovery_holes"]
    finally:
        destroy(hole_home)
    print(
        f"hole_fired={hole_fired} holes={hole_sub['recovery_holes']} "
        f"rc={hole_obs['returncode']}"
    )
    if hole_obs["returncode"] != 0:
        print("FAILED:REL-0022-probe1 hole-mutation install failed")
        return 1
    if not hole_fired:
        print("FAILED:REL-0022-probe1 unrecorded side effect did not report a hole")
        return 1

    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:REL-0022-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:REL-0022-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:REL-0022" not in text:
        print("FAILED:REL-0022-probe1 sentinel absent")
        return 1
    if not (doc.get("detector_control") or {}).get("pass"):
        print("FAILED:REL-0022-probe1 receipt detector_control.pass is not true")
        return 1
    if not (doc.get("hole_mutation") or {}).get("fired"):
        print("FAILED:REL-0022-probe1 receipt hole_mutation.fired is not true")
        return 1
    if not doc.get("zero_hole_finding_permitted"):
        print("FAILED:REL-0022-probe1 zero-hole finding was not detector-gated")
        return 1

    print("SUCCESS:REL-0022-probe1 detector-control and recovery-hole")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
