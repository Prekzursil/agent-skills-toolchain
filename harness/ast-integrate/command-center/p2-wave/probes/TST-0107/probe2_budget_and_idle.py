#!/usr/bin/env python3
"""Probe 2: spawn budget per invocation, idle gated probes pay zero.

Both-states: the over-budget jq mutant is caught, and removing the idle
gate makes idle pay nested spawns. That proves the budget/gate are
load-bearing rather than a silent no-op.
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
    report = H.budget_bundle()
    print(json.dumps(report, sort_keys=True))
    if not report.get("pass"):
        print("FAILED:TST-0107-probe2 budget or idle gate")
        return 1
    receipt = H.receipt_shape_ok()
    if not receipt.get("pass"):
        print("FAILED:TST-0107-probe2 receipt")
        print(json.dumps(receipt, sort_keys=True))
        return 1
    print(
        "inproc_within_budget=True overbudget_mutant_caught=True "
        "idle_gated_zero=True idle_ungated_spawns=True "
        "slow_render_cancelled=True schema_garbage_rejected=True"
    )
    print(f"SUCCESS:{UNIT}-probe2 spawn budget, idle zero, cancel, schema")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
