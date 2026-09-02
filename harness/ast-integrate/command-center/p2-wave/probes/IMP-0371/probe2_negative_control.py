#!/usr/bin/env python3
"""Probe 2: adversarial negative control.

Re-derives the falsifiable question from the catalog tests, not from the
author's summary: can a candidate reach implementation without a
reproduction receipt? With the gate on, no. With the gate removed, yes —
and that ungated advance is what proves the gate was load-bearing.

Also: mutating candidate fields to look confirmed does not bypass the
issued-receipt register.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

UNIT = "IMP-0371"


def main() -> int:
    report = H.negative_control()
    print(json.dumps(report, sort_keys=True))
    if not report.get("pass"):
        print("FAILED:IMP-0371-probe2 negative control")
        print(json.dumps(report.get("checks") or report, indent=2)[:2000])
        return 1
    print(
        "gated_unreproduced_blocked=True "
        "spoofed_fields_blocked=True "
        "ungated_unreproduced_advanced=True "
        "ungated_audit_held=False"
    )
    print(f"SUCCESS:{UNIT}-probe2 negative control remove-gate unreproduced advances")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
