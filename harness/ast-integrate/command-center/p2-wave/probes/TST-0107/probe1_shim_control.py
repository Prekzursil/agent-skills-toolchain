#!/usr/bin/env python3
"""Probe 1: PATH-shim detector control. A text grep is not an acceptable detector.

The catalog names test_shim_catches_a_known_spawn. A zero spawn count is
refused until this control has fired on the same shim.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

UNIT = "TST-0107"


def main() -> int:
    report = H.detector_bundle()
    print(json.dumps(report, sort_keys=True))
    if not report.get("pass"):
        print("FAILED:TST-0107-probe1 detector control")
        return 1
    receipt = H.receipt_shape_ok()
    if not receipt.get("pass"):
        print("FAILED:TST-0107-probe1 receipt")
        print(json.dumps(receipt, sort_keys=True))
        return 1
    print(
        "detector=proven method=PATH-shim "
        "grep_trap_mentions_jq=True shim_jq_on_inproc=0"
    )
    print(f"SUCCESS:{UNIT}-probe1 shim catches known spawn; grep is not detector")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
