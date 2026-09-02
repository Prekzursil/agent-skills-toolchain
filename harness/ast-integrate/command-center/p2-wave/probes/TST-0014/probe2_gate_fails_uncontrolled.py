#!/usr/bin/env python3
"""Probe 2: CI gate fails on an uncontrolled detector (independent of probe 1).

all-controlled fixture -> gate exit 0
uncontrolled fixture (extra hook with no registry row) -> gate exit 1
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from detector_control.enumerate import FIXTURES  # noqa: E402
from detector_control.gate import run_gate  # noqa: E402

UNIT = "TST-0014"


def test_ci_gate_fails_on_an_uncontrolled_detector() -> dict:
    good = run_gate(
        root=FIXTURES / "all-controlled",
        skip_self_fixtures=False,
        threshold=0,
        census_only=False,
    )
    bad = run_gate(
        root=FIXTURES / "uncontrolled",
        skip_self_fixtures=False,
        threshold=0,
        census_only=False,
    )
    ok = (
        good["detector_control"]["fired"] is True
        and bad["detector_control"]["fired"] is True
        and good["exit_code"] == 0
        and good["census"]["uncontrolled_count"] == 0
        and good["reason"] == "all-controlled"
        and bad["exit_code"] == 1
        and bad["reason"] == "uncontrolled-detectors"
        and "uncontrolled-orphan-hook" in (bad.get("uncontrolled_ids") or [])
        and good["detector_control"]["known_present_run_first"] is True
        and bad["detector_control"]["fired_before_absence_reported"] is True
    )
    return {
        "id": "test_ci_gate_fails_on_an_uncontrolled_detector",
        "pass": ok,
        "good_exit": good["exit_code"],
        "good_reason": good["reason"],
        "good_uncontrolled": good["census"]["uncontrolled_count"],
        "bad_exit": bad["exit_code"],
        "bad_reason": bad["reason"],
        "bad_uncontrolled_ids": bad.get("uncontrolled_ids"),
        "enumerator_control_fired_both": (
            good["detector_control"]["fired"] and bad["detector_control"]["fired"]
        ),
    }


def main() -> int:
    result = test_ci_gate_fails_on_an_uncontrolled_detector()
    payload = {
        "probe": "probe2-gate-fails-uncontrolled",
        "unit_id": UNIT,
        "pass": result["pass"],
        **{k: v for k, v in result.items() if k != "pass"},
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"good_exit={result['good_exit']} bad_exit={result['bad_exit']} "
        f"orphan={result['bad_uncontrolled_ids']}"
    )
    if not result["pass"]:
        print("FAILED:TST-0014-probe2 CI gate did not fail on uncontrolled detector")
        return 1
    print("SUCCESS:TST-0014-probe2 CI gate fails on an uncontrolled detector")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
