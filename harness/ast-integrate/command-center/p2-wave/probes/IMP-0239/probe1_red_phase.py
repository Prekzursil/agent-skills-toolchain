#!/usr/bin/env python3
"""Named probe 1: red-phase receipt required before implementation (both-states).

Bad state: implementation offered with no red receipt, or a never-red suite.
Good state: live red run names the missing symbol, then a separate green run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from blueprints.tdd import (  # noqa: E402
    MISSING_SYMBOL,
    accept_implementation,
    flagship_e2e,
    prove_red_phase,
)
from blueprints.tdd import FIXTURES as TDD_FIXTURES  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0239-probe1 {msg}")
    return 1


def main() -> int:
    e2e = flagship_e2e()
    red = e2e["red"]
    green = e2e["green"]
    if not e2e.get("ok"):
        return fail(f"flagship e2e failed red={red} green={green}")
    if red.get("verdict") != "RED":
        return fail(f"red verdict {red.get('verdict')}")
    if MISSING_SYMBOL not in (red.get("failure_output") or ""):
        return fail("red failure output did not name the missing symbol")
    if green.get("verdict") != "GREEN" or not green.get("separate_run"):
        return fail(f"green phase not a separate passing run: {green}")

    no_receipt = accept_implementation(None, TDD_FIXTURES / "green")
    if no_receipt.get("accepted") or no_receipt.get("reason") != "red-phase-receipt-required":
        return fail(f"missing receipt was not rejected: {no_receipt}")

    fake_green = {
        "ok": True,
        "verdict": "GREEN",
        "implementation_present": False,
        "failure_names_symbol": False,
        "run_id": "not-a-red-run",
    }
    never_red = accept_implementation(fake_green, TDD_FIXTURES / "green")
    if never_red.get("accepted"):
        return fail(f"never-red receipt was accepted: {never_red}")

    already = prove_red_phase(TDD_FIXTURES / "test_frobnicate.py", TDD_FIXTURES / "green")
    if already.get("ok") or already.get("reason") != "implementation-already-present":
        return fail(f"red phase against green subject not refused: {already}")

    payload = {
        "probe": "probe1-red-phase",
        "unit_id": "IMP-0239",
        "required_symbol": MISSING_SYMBOL,
        "red_verdict": red["verdict"],
        "red_exit_code": red["exit_code"],
        "failure_names_symbol": True,
        "green_verdict": green["verdict"],
        "separate_green_run": True,
        "missing_receipt_rejected": True,
        "never_red_rejected": True,
        "already_implemented_refused": True,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "red=RED named_symbol=True green=GREEN separate=True "
        "missing_receipt_rejected=True never_red_rejected=True"
    )
    print("SUCCESS:IMP-0239-probe1 red-phase receipt required (both-states)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
