#!/usr/bin/env python3
"""Probe 1: both-states, extraction-control, live detector vs FAILURE-MODES.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import compose  # noqa: E402
import detector  # noqa: E402
import scenario as S  # noqa: E402

REPO = HERE.parents[3]
ART = REPO / "command-center/phase3/A9/FAILURE-MODES.json"


def main() -> int:
    ctrl = S.both_states()
    checks = [
        ("planted_fires", ctrl.get("planted_fires")),
        ("clean_silent", ctrl.get("clean_silent")),
        ("empty_fails_extraction", ctrl.get("empty_fails_extraction")),
        ("naive_union_fires", ctrl.get("naive_union_fires")),
        ("extraction_control_clean", ctrl["clean"].get("extraction_control_ok")),
        ("extraction_control_planted", ctrl["planted"].get("extraction_control_ok")),
    ]
    for name, ok in checks:
        print(f"{name}={ok}")
        if not ok:
            print(f"FAILED:ARC-0061-probe1 {name}")
            return 1

    planted_caps = {f["capability"] for f in ctrl["planted"]["findings"]}
    if "authorization" not in planted_caps:
        print("FAILED:ARC-0061-probe1 planted finding missing authorization")
        return 1
    naive_caps = {f["capability"] for f in ctrl["naive_union"]["findings"]}
    if "capability-declaration" not in naive_caps:
        print("FAILED:ARC-0061-probe1 naive union missed capability-declaration")
        return 1

    # Re-run detector.py on the on-disk fixtures, not only in-memory objects.
    compose.write_fixtures(HERE)
    fx = HERE / "fixtures"
    clean_file = detector.scan_path(fx / "clean.json")
    dup_file = detector.scan_path(fx / "duplicate.json")
    empty_file = detector.scan_path(fx / "empty.json")
    if clean_file["status"] != "CLEAN" or dup_file["status"] != "DUPLICATE":
        print("FAILED:ARC-0061-probe1 on-disk fixture scan")
        return 1
    if empty_file["status"] != "EXTRACTION-FAILED":
        print("FAILED:ARC-0061-probe1 empty fixture not extraction-failed")
        return 1

    if not ART.is_file():
        print("FAILED:ARC-0061-probe1 FAILURE-MODES.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0061-probe1 self-declared {doc.get('state')}")
        return 1
    live = doc.get("detector_control") or {}
    if int(live.get("clean_duplicate_count")) != int(ctrl["clean"]["duplicate_count"]):
        print("FAILED:ARC-0061-probe1 artifact clean count drift")
        return 1
    if int(live.get("planted_duplicate_count")) != int(ctrl["planted"]["duplicate_count"]):
        print("FAILED:ARC-0061-probe1 artifact planted count drift")
        return 1
    if live.get("a9_design_present") is True:
        print("FAILED:ARC-0061-probe1 artifact claims A9 DESIGN present")
        return 1
    if "SUCCESS:ARC-0061" not in ART.read_text(encoding="utf-8"):
        print("FAILED:ARC-0061-probe1 sentinel absent")
        return 1
    print(
        "clean="
        + str(ctrl["clean"]["duplicate_count"])
        + " planted="
        + str(ctrl["planted"]["duplicate_count"])
        + " naive="
        + str(ctrl["naive_union"]["duplicate_count"])
        + " a9_design="
        + str(ctrl["a9_design_present"])
    )
    print("SUCCESS:ARC-0061-probe1 both-states extraction-control live detector")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
