#!/usr/bin/env python3
"""Probe 1: preflight must report DOWN for a wrong endpoint and UP for a known-good one.

A preflight that returns UP for both is not measuring reachability.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import preflight as P  # noqa: E402

ART = (
    P.REPO
    / "command-center"
    / "research"
    / "deep-research-design"
    / "RES-0168-source-class-backend-routing-preflight.json"
)


def main() -> int:
    live = P.detector_control(mutant_always_up=False)
    mutant = P.detector_control(mutant_always_up=True)
    print(
        json.dumps(
            {
                "probe": "probe1-detector-control",
                "unit_id": "RES-0168",
                "live_pass": live["pass"],
                "good_status": live["good"]["reported_status"],
                "bad_status": live["bad"]["reported_status"],
                "bad_tcp_status": live["bad_tcp"]["reported_status"],
                "good_http": live["good"]["observed_http_status"],
                "bad_error_type": live["bad"]["observed_error_type"],
                "mutant_always_up_pass": mutant["pass"],
                "mutant_bad_status": mutant["bad"]["reported_status"],
            },
            sort_keys=True,
        )
    )
    if not live["pass"]:
        print("FAILED:RES-0168-probe1 live detector did not discriminate UP vs DOWN")
        return 1
    if live["good"]["reported_status"] != "UP":
        print("FAILED:RES-0168-probe1 known-good endpoint was not UP")
        return 1
    if live["bad"]["reported_status"] != "DOWN":
        print("FAILED:RES-0168-probe1 deliberately wrong endpoint was not DOWN")
        return 1
    if live["bad_tcp"]["reported_status"] != "DOWN":
        print("FAILED:RES-0168-probe1 refused TCP endpoint was not DOWN")
        return 1
    if mutant["pass"]:
        print("FAILED:RES-0168-probe1 always-UP mutant was accepted")
        return 1
    if mutant["bad"]["reported_status"] != "UP":
        print("FAILED:RES-0168-probe1 mutant did not report UP for the bad endpoint")
        return 1
    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        control = (doc.get("detector_control") or {})
        if control.get("good_status") != "UP" or control.get("bad_status") != "DOWN":
            print("FAILED:RES-0168-probe1 artifact detector_control is not UP/DOWN")
            return 1
        if "SUCCESS:RES-0168" not in ART.read_text(encoding="utf-8"):
            print("FAILED:RES-0168-probe1 artifact missing SUCCESS:RES-0168")
            return 1
    print("SUCCESS:RES-0168-probe1 detector reports DOWN for wrong endpoint and UP for known-good")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
