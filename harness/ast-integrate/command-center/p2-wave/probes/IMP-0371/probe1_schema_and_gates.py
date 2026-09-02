#!/usr/bin/env python3
"""Probe 1: candidate schema and stage gates, plus the 3-of-10 flaky control.

Starts from the tests the catalog names, not from a summary of intake.py.
Does not rewrite the catalog receipt.
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
    schema = H.schema_and_stage_gates()
    flaky = H.flaky_control()
    print(json.dumps({"schema_and_gates": schema, "flaky_control": flaky}, sort_keys=True))
    if not schema.get("pass"):
        print("FAILED:IMP-0371-probe1 schema or stage-gate check")
        print(json.dumps(schema.get("checks") or schema, indent=2)[:2000])
        return 1
    if not flaky.get("pass"):
        print("FAILED:IMP-0371-probe1 flaky 3-of-10 control")
        print(json.dumps(flaky.get("checks") or flaky, indent=2)[:2000])
        return 1
    print(
        "schema_ok=True flaky_3_of_10=flaky baseline_accepted=False "
        "confirmed_10_of_10=implementation audit_held=True"
    )
    print(f"SUCCESS:{UNIT}-probe1 candidate schema, stage gates, flaky 3-of-10")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
