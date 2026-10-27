#!/usr/bin/env python3
"""IMP-0371 probe2: negative control + spoof resistance (catalog test 3).

Verifies against the LIVE tools/selfimprove/intake.py:
  NC1 negative control: with the reproduction gate REMOVED, an unreproduced
     (0/10) candidate DOES reach implementation - and the stage-gate audit
     reports held=false listing the candidate, proving the gate is
     load-bearing. The same candidate is blocked when the gate is on.
  NC2 spoof: planted confirmed fields (classification=confirmed,
     baseline_accepted=true) without an issued reproduction receipt do NOT
     bypass the issued-receipt register; a flaky candidate whose fields are
     later edited to confirmed is also blocked.

Exits 0 and prints SUCCESS:IMP-0371-probe2 only when every assertion holds.
"""
from __future__ import annotations

import io
import json
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import harness  # noqa: E402

UNIT = "IMP-0371"


def main() -> int:
    failures: list[str] = []

    # --- NC1: gate removed -> unreproduced ADVANCES (control fires) ---
    ungated = harness.run_ungated_negative_control()
    if ungated["allowed_advances_to_implementation"] != 1:
        failures.append("nc:gate-removed did not let unreproduced candidate advance")
    if ungated["gate_enforced"]:
        failures.append("nc:gate_enforced=true in ungated run")
    if not ungated["advanced_without_confirmed_receipt"]:
        failures.append("nc:audit did not list the ungated advance")
    if ungated["held"]:
        failures.append("nc:audit held=true in ungated run (control did not fire)")

    # --- same candidate blocked when gate is ON ---
    unrep = harness.run_gated_unreproduced_run()
    if unrep["blocked_reason"] != "unreproduced-not-accepted-as-baseline":
        failures.append(f"nc:gated twin not blocked: {unrep['blocked_reason']}")
    if not unrep["held"]:
        failures.append("nc:gated twin audit did not hold")

    # --- NC2: spoofed fields do not bypass the issued-receipt register ---
    spoof = harness.run_spoofed_fields_run()
    if spoof["spoof_blocked_reason"] != "missing-reproduction-receipt":
        failures.append(f"spoof:planted confirmed fields bypassed gate: {spoof['spoof_blocked_reason']}")
    if spoof["flaky_spoof_blocked_reason"] != "flaky-not-accepted-as-baseline":
        failures.append(
            f"spoof:edited flaky candidate bypassed gate: {spoof['flaky_spoof_blocked_reason']}"
        )
    if not spoof["held"]:
        failures.append("spoof:audit did not hold under spoof attempts")

    result = {
        "unit_id": UNIT,
        "probe": "probe2-negative-control",
        "pass": not failures,
        "ungated_negative_control": ungated,
        "gated_unreproduced_twin": unrep,
        "spoofed_fields_run": spoof,
        "failures": failures,
    }
    print(json.dumps(result, indent=1))
    if failures:
        for f in failures:
            print(f"FAILED:{UNIT}-probe2 {f}")
        return 1
    print(
        f"SUCCESS:{UNIT}-probe2 ungated unreproduced advances (control fires); "
        "spoofed confirmed fields still blocked"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
