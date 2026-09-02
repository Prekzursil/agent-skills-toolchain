#!/usr/bin/env python3
"""Probe 2: channel-pinned client resolves only within its channel (10 cases).

Independent signal (2) of IMP-0071 evidence_requirement: a 10-case matrix of
pin-stable, pin-beta, pin-canary, and cross-channel refusal.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "marketplace"))

import channels as C  # noqa: E402

UNIT = "IMP-0071"
RECEIPT = REPO / "command-center/receipts/IMP-0071.json"


def _fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    report = C.run_pin_matrix()
    if report["cases"] != 10:
        return _fail(f"matrix size {report['cases']} want=10")
    if not report["pass"] or report["passed"] != 10:
        return _fail(f"failed cases={report['failed']}")

    if RECEIPT.is_file():
        text = RECEIPT.read_text(encoding="utf-8")
        if "SUCCESS:IMP-0071" not in text:
            return _fail("receipt missing SUCCESS:IMP-0071")
        if "10-case" not in text and "10 case" not in text and "PIN_MATRIX" not in text:
            # Accept either phrasing of the matrix in the receipt.
            if '"cases": 10' not in text and "cases=10" not in text:
                return _fail("receipt does not record the 10-case pin matrix")

    payload = {
        "probe": "probe2-channel-pin-matrix",
        "unit_id": UNIT,
        "cases": report["cases"],
        "passed": report["passed"],
        "failed": report["failed"],
        "results": report["results"],
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(f"matrix cases=10 passed=10 failed=0")
    print(f"SUCCESS:{UNIT}-probe2 channel-pin 10-case matrix")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
