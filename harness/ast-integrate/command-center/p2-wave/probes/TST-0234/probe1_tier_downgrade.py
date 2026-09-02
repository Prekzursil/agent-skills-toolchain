#!/usr/bin/env python3
"""Probe 1: detector control — downgrade one arm's model tier and block.

Matched Claude-vs-Codex (T1/T1, identical tools/budget/file-transport/drivers)
is CONFOUND-CLEAR. Replacing the Claude response model with sonnet (T2) makes
the confound report block the comparative verdict. Other axes have the same
both-states polarity. Re-reading a receipt verifies nothing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from testinfra.test_cross_vendor_confound import (  # noqa: E402
    test_tier_downgrade_blocks_comparative_verdict,
)

UNIT = "TST-0234"


def main() -> int:
    result = test_tier_downgrade_blocks_comparative_verdict()
    payload = {
        "probe": "probe1-tier-downgrade",
        "unit_id": UNIT,
        "pass": result["pass"],
        "matched": result["matched"],
        "downgraded": result["downgraded"],
        "two_state": result["two_state"],
        "other_axis_controls": {
            k: {"verdict": v["verdict"], "reason": v["reason"]}
            for k, v in result["other_axis_controls"].items()
        },
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not result["pass"]:
        print("FAILED:TST-0234-probe1 tier-downgrade detector did not discriminate")
        return 1
    print(
        "SUCCESS:TST-0234-probe1 matched pair is CONFOUND-CLEAR; "
        "sonnet downgrade blocks on MODEL-TIER-CONFOUND"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
