#!/usr/bin/env python3
"""Probe 1: static scan for unquoted caret-bearing git revisions through PowerShell.

Signal (a): estate scan. Both-states: control-bad must fire, control-good must not.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scan as S  # noqa: E402

ART = REPO / "command-center/receipts/TST-0188.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0188-probe1 {msg}")
    return 1


def main() -> int:
    controls = S.scan_controls()
    if not controls["fired_on_bad"]:
        return fail(
            f"control-bad did not fire hazards={controls['bad_hazard_count']}"
        )
    if not controls["silent_on_good"]:
        return fail(
            f"control-good produced hazards={controls['good_hazard_count']} "
            f"{controls['good_hits']}"
        )
    estate = S.scan_tree(REPO)
    if estate["hazard_count"] != 0:
        return fail(f"estate hazards={estate['hazards']}")
    if estate["files_scanned"] < 1:
        return fail("scanned zero files")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        pub = ((doc.get("evidence") or {}).get("static_scan") or {})
        if pub.get("hazard_count") != 0:
            return fail("receipt static_scan.hazard_count is not zero")
        if not pub.get("fired_on_bad"):
            return fail("receipt missing both-states fired_on_bad")
        if pub.get("silent_on_good") is not True:
            return fail("receipt missing both-states silent_on_good")
        blob = json.dumps(doc)
        if "SUCCESS:TST-0188" not in blob:
            return fail("receipt sentinel absent")

    summary = {
        "probe": "probe1-static-scan",
        "unit_id": "TST-0188",
        "files_scanned": estate["files_scanned"],
        "hazard_count": estate["hazard_count"],
        "fired_on_bad": True,
        "silent_on_good": True,
        "bad_hazard_count": controls["bad_hazard_count"],
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"files_scanned={estate['files_scanned']} hazards={estate['hazard_count']} "
        f"control_bad={controls['bad_hazard_count']} control_good={controls['good_hazard_count']}"
    )
    print("SUCCESS:TST-0188-probe1 static scan zero unquoted caret git sites")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
