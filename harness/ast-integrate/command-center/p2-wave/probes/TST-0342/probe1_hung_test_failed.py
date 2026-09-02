#!/usr/bin/env python3
"""Probe 1: a test that sleeps past the timeout produces FAILED, not a stuck run."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from testinfra.test_timeout_budget import (  # noqa: E402
    test_hung_test_produces_failed_not_stuck,
)


def main() -> int:
    result = test_hung_test_produces_failed_not_stuck()
    payload = {
        "probe": "probe1-hung-test-failed-not-stuck",
        "unit_id": "TST-0342",
        "pass": result["pass"],
        "test_hung_test_produces_failed_not_stuck": result,
    }
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    if not result["pass"]:
        print("FAILED:TST-0342-probe1 hung test did not produce FAILED")
        return 1
    hung = result["hung_control"]["hung"]
    print(
        f"timed_out={hung['timed_out']} outcome={hung['outcome']} "
        f"duration_s={hung['duration_s']:.3f} "
        f"mutant_still_running={result['hung_control']['mutant_still_running']}"
    )
    print("SUCCESS:TST-0342-probe1 hung test produces FAILED, not a stuck run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
