#!/usr/bin/env python3
"""Probe 1: run mock workers through each fan-in barrier.

Records each barrier's verdict plus the exact filesystem state. A worker
that does write a valid artifact must be accepted (detector control). An
exit-zero-is-complete mutant must accept the missing-artifact worker so
the rejection is not a tautology.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from injection import NEAR_MISS, UNIT, run_campaign  # noqa: E402

SENTINEL = f"SUCCESS:{UNIT}-probe1"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    camp = run_campaign()
    checks = camp["checks"]
    inv = camp["inventory"]
    payload = {
        "unit_id": UNIT,
        "probe": "probe1-barrier-injection",
        "method": camp["method_probe1"],
        "inventory": inv,
        "checks": checks,
        "worker_exit_codes": {
            k: camp["trees"][k]["worker"]["exit_code"] for k in camp["trees"]
        },
        "file_reprs": {k: camp["trees"][k]["file_reprs"] for k in camp["trees"]},
        "production_missing_reasons": [
            r["barrier"]["reason"]
            for r in camp["barrier_rows"]
            if r["kind"] == "missing"
        ],
        "production_valid_ok": [
            r["recorded_complete"]
            for r in camp["barrier_rows"]
            if r["kind"] == "valid"
        ],
        "near_miss_kinds": list(NEAR_MISS),
        "mutant_missing_complete": next(
            r["recorded_complete"]
            for r in camp["mutant_rows"]
            if r["kind"] == "missing"
        ),
        "pass": camp["pass"],
    }
    print(json.dumps(payload, sort_keys=True))
    if not checks["seven_production_barriers"]:
        return fail(f"barrier inventory {inv}")
    if not checks["workers_all_exit_zero"]:
        return fail(f"workers did not all exit 0: {payload['worker_exit_codes']}")
    if not checks["missing_rejected_by_production"]:
        return fail("a production barrier recorded the missing-artifact worker complete")
    if not checks["near_miss_rejected_by_production"]:
        return fail("a production barrier recorded a near-miss path complete")
    if not checks["valid_accepted_by_production"]:
        return fail("detector control: valid worker was not accepted")
    if not checks["mutant_accepts_missing"]:
        return fail("exit-zero mutant did not accept the missing-artifact worker")
    if not camp["pass"]:
        return fail(f"campaign checks {checks}")
    print(
        "barriers={n} missing_rejected=True valid_accepted=True "
        "near_miss_rejected=True mutant_accepts_missing=True".format(
            n=inv["consider_count"]
        )
    )
    print(f"{SENTINEL} exit-zero missing/near-miss rejected; valid control accepted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
