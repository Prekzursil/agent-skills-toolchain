#!/usr/bin/env python3
"""Probe 1: detector-control on planted pathology, then silence on clean.

The known-present fixture is scanned FIRST. Absence is not reported until
that scan fires. Both runs are printed verbatim.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402

OUT = HERE / "probe1-both-states.raw.json"
PLANTED = "planted-filler-consent.json"
CLEAN = "clean-yield-only-nothing-to-add.json"


def compact(result: dict) -> dict:
    return {
        "fixture_id": result["fixture_id"],
        "file": result.get("file"),
        "fired": result["fired"],
        "silent": result["silent"],
        "fired_seats": result["fired_seats"],
        "reasons": {
            s: result["seats"][s]["reasons"]
            for s in result["roster"]
            if result["seats"][s]["reasons"]
        },
        "runtime": result["runtime"],
    }


def main() -> int:
    planted = D.scan_file(PLANTED)
    planted["file"] = PLANTED
    planted_c = compact(planted)
    print("DETECTOR-CONTROL planted-first")
    print(json.dumps(planted_c, sort_keys=True))
    if not planted["fired"]:
        print("FAILED:CNL-0089-probe1 planted pathology did not fire")
        return 1
    if "D" not in planted["fired_seats"]:
        print("FAILED:CNL-0089-probe1 expected seat D")
        return 1
    reasons = planted["seats"]["D"]["reasons"]
    if "filler-masquerade" not in reasons or "consent-by-silence" not in reasons:
        print("FAILED:CNL-0089-probe1 missing filler or consent reasons", reasons)
        return 1

    clean = D.scan_file(CLEAN)
    clean["file"] = CLEAN
    clean_c = compact(clean)
    print("KNOWN-GOOD after detector-control")
    print(json.dumps(clean_c, sort_keys=True))
    if not clean["silent"]:
        print("FAILED:CNL-0089-probe1 clean nothing-to-add fixture fired")
        return 1
    if clean["seats"]["D"]["structured_yield"] < 1:
        print("FAILED:CNL-0089-probe1 clean D was not a structured yield")
        return 1
    if "D" in set(clean["agreeing"]):
        print("FAILED:CNL-0089-probe1 yield-only seat was counted as agreeing")
        return 1

    doc = {
        "detector_control_first": True,
        "planted": planted_c,
        "clean": clean_c,
        "fired_on_planted": True,
        "silent_on_clean": True,
        "pass": True,
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "fired_on_planted=True silent_on_clean=True "
        "detector_control_first=True"
    )
    print("SUCCESS:CNL-0089-probe1 both-states silence vs disengagement")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
