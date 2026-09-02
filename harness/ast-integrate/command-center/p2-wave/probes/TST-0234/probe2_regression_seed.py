#!/usr/bin/env python3
"""Probe 2: regression seed — Claude-vs-Codex that was sonnet-driver vs opus-driver.

Evidence is (a) the confound report equality table and (b) the raw invocation
records. Re-deriving the table from those records must match. A request-side
naive checker incorrectly CLEARS the seed; the response-side gate blocks it
as DRIVER-CONFOUND. Relabeling claimed vendors does not clear the block.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from testinfra.test_cross_vendor_confound import (  # noqa: E402
    test_regression_seed_sonnet_driver_vs_opus_driver,
)

UNIT = "TST-0234"


def main() -> int:
    result = test_regression_seed_sonnet_driver_vs_opus_driver()
    payload = {
        "probe": "probe2-regression-seed",
        "unit_id": UNIT,
        "pass": result["pass"],
        "seed_report": result["seed_report"],
        "raw_invocations": result["raw_invocations"],
        "naive_request_side": result["naive_request_side"],
        "recompute_matches": result["recompute_matches"],
        "two_state": result["two_state"],
        "absent_driver_blocks": result["absent_driver_blocks"],
        "declared_only_blocks": result["declared_only_blocks"],
        "relabel_does_not_clear": result["relabel_does_not_clear"],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not result["pass"]:
        print("FAILED:TST-0234-probe2 regression seed was not blocked as DRIVER-CONFOUND")
        return 1
    print(
        "SUCCESS:TST-0234-probe2 sonnet-driver vs opus-driver blocks; "
        "request-side checker falsely clears; recompute matches raw records"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
