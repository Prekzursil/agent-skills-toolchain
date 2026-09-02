#!/usr/bin/env python3
"""Probe 1: zero-collected and below-minimum runs FAIL regardless of runner rc.

Required proofs:
  * Point a runner at an empty directory -> floor FAIL (zero-collected).
    unittest.TextTestRunner.wasSuccessful() is True on 0 tests (the green-not-live
    API); Python 3.12's CLI exits 5; a naive wrapper mapping {0,5}->0 is still
    overridden by the floor.
  * Deselect most of the 4-test fixture (run only test_alpha) with min=3 ->
    floor FAIL (below-minimum) while the runner itself exits 0.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SUITE = HERE / "fixtures" / "suite"
ART = REPO / "command-center/receipts/TST-0350.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})

sys.path.insert(0, str(REPO / "tools" / "command-center"))
import suitefloor as F  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:TST-0350-probe1 {msg}")
    return 1


def main() -> int:
    zero = F.measure_zero_collected_green()
    print(json.dumps({"zero_collected": zero}, sort_keys=True))
    api = zero["api"]
    api_floor = zero["api_floor"]
    if int(api["collected"]) != 0:
        return fail(f"empty dir collected {api['collected']}, want 0")
    if api["was_successful"] is not True:
        return fail("empty TextTestRunner wasSuccessful was not True (defect not measured)")
    if api_floor["verdict"] != "FAIL" or "zero-collected" not in api_floor["reasons"]:
        return fail(f"empty-dir floor did not FAIL zero-collected: {api_floor}")
    if not api_floor["floor_overrides_runner"]:
        return fail("floor did not override the empty-suite API green")

    cli_floor = zero["cli_floor"]
    if int(zero["cli"]["collected"]) != 0:
        return fail(f"unittest discover empty collected {zero['cli']['collected']}")
    if cli_floor["verdict"] != "FAIL" or "zero-collected" not in cli_floor["reasons"]:
        return fail(f"CLI empty-dir floor did not FAIL: {cli_floor}")
    if not cli_floor["naive_runner_green"]:
        return fail("naive {0,5}->green wrapper was not the measured green-not-live class")
    if not cli_floor["floor_overrides_runner"]:
        return fail("floor did not override naive-green CLI rc")

    one = F.run_unittest_cli(SUITE, ["test_demo.FloorDemo.test_alpha"])
    print(json.dumps({"below_min_run": {"rc": one["rc"], "collected": one["collected"]}}, sort_keys=True))
    if one["rc"] != 0:
        return fail(f"single-test run rc={one['rc']} (want 0 so the floor, not the runner, is the fail)")
    if int(one["collected"]) != 1:
        return fail(f"single-test collected {one['collected']}, want 1")
    below = F.evaluate(
        collected=int(one["collected"]),
        min_collected=3,
        runner_exit_code=int(one["rc"]),
        runner_was_successful=one["rc"] == 0,
    )
    print(json.dumps({"below_min_floor": below}, sort_keys=True))
    if below["verdict"] != "FAIL" or "below-minimum" not in below["reasons"]:
        return fail(f"deselect-most-of-suite did not FAIL below-minimum: {below}")
    if below["runner_exit_code"] != 0:
        return fail("below-minimum runner was not green; the floor would be redundant")

    undeclared = F.evaluate(collected=4, min_collected=None)
    if undeclared["verdict"] != "FAIL" or "undeclared-minimum" not in undeclared["reasons"]:
        return fail(f"missing min was not a finding: {undeclared}")

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if str(doc.get("state") or "").upper() in NOT_DELIVERING:
            return fail(f"self-declared {doc.get('state')}")
        if "SUCCESS:TST-0350" not in text:
            return fail("receipt sentinel-absent")

    print("zero_collected_fails=True below_minimum_fails=True runner_was_green=True")
    print("SUCCESS:TST-0350-probe1 zero-collected and below-minimum FAIL regardless of runner rc")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
