#!/usr/bin/env python3
"""Probe 1: mismatched nested stopping, plus control and bounded deadlock.

Runs the nested fan-in. Records child/parent terminal states and whether
the elapsed behaviour is block, accept, or spin. The shared-predicate path
must BLOCK on mismatch, COMPLETE on a consistent nesting, and detect
deadlock by a recorded timeout. The council-local mutant must ACCEPT.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nested_fanin as N  # noqa: E402

UNIT = "ADV-0102"


def main() -> int:
    bundle = N.scenarios()
    checks = N.assertions(bundle)
    ms = bundle["mismatch_shared"]
    ml = bundle["mismatch_local"]
    ctrl = bundle["control_consistent"]
    dl = bundle["deadlock"]
    payload = {
        "probe": "probe1-mismatched-nesting",
        "unit_id": UNIT,
        "method": "live-nested-fan-in-with-shared-reducer-receipts",
        "shared_symbol": N.SHARED_SYMBOL,
        "timeout_seconds": bundle["timeout_seconds_recorded"],
        "timeout_ticks": bundle["timeout_ticks_recorded"],
        "mismatch_shared": {
            "child_complete": ms["child_complete"],
            "parent_complete": ms["parent_complete"],
            "elapsed_behaviour": ms["elapsed_behaviour"],
            "terminal": ms["terminal"],
            "child_expr": ms["child_expr"],
            "parent_expr": ms["parent_expr"],
            "ticks": ms["ticks"],
            "timeout_fired": ms["timeout_fired"],
        },
        "mismatch_local_mutant": {
            "child_complete": ml["child_complete"],
            "parent_complete": ml["parent_complete"],
            "elapsed_behaviour": ml["elapsed_behaviour"],
            "terminal": ml["terminal"],
        },
        "control_consistent": {
            "child_complete": ctrl["child_complete"],
            "parent_complete": ctrl["parent_complete"],
            "terminal": ctrl["terminal"],
            "elapsed_behaviour": ctrl["elapsed_behaviour"],
        },
        "deadlock": {
            "terminal": dl["terminal"],
            "timeout_fired": dl["timeout_fired"],
            "timeout_seconds": dl["timeout_seconds"],
            "ticks": dl["ticks"],
            "child_complete": dl["child_complete"],
            "parent_complete": dl["parent_complete"],
        },
        "receipts": {
            "complete_verdict": bundle["receipts"]["complete_receipt"]["verdict"],
            "incomplete_verdict": bundle["receipts"]["incomplete_receipt"]["verdict"],
        },
        "checks": {name: bool(ok) for name, ok in checks},
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    for name, ok in checks:
        print(f"{name}={ok}")
        if not ok:
            print(f"FAILED:{UNIT}-probe1 {name}")
            return 1
    print(
        "SUCCESS:ADV-0102-probe1 mismatch blocks; control completes; "
        "deadlock timeout recorded; local mutant accepts"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
