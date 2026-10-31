#!/usr/bin/env python3
"""IMP-0371 probe1: candidate schema and stage gates (catalog tests 1 + 2).

Verifies against the LIVE tools/selfimprove/intake.py:
  T1 unit: candidate schema validation catches missing fields + bad kind,
     and the stage gates admit only a confirmed baseline.
  T2 control: a flaky failure (3 of 10) is labelled flaky and is NOT
     accepted as a baseline - advance_to_implementation raises
     GateBlocked(flaky-not-accepted-as-baseline).
  E1 evidence: a stage-gate audit proving no candidate advanced to
     implementation without a reproduction receipt.

Exits 0 and prints SUCCESS:IMP-0371-probe1 only when every assertion holds.
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

    # --- candidate schema (T1a) ---
    sp = harness.schema_errors_probe()
    if not sp["clean_ok"]:
        failures.append(f"schema:valid candidate flagged: {sp['clean_ok']}")
    missing = {"missing:candidate_id", "missing:stage", "missing:classification"}
    if not missing.issubset(set(sp["stripped_errors"])):
        failures.append(f"schema:missing fields not detected: {sp['stripped_errors']}")
    if not sp["bad_kind_detected"]:
        failures.append("schema:bad kind not detected")

    # --- stage gates + flaky control (T1b + T2) ---
    gated = harness.run_gated_confirmed_run()
    flaky_row, confirmed_row = gated["repeat_counts"]
    if flaky_row["classification"] != "flaky":
        failures.append(f"gate:3-of-10 not labelled flaky: {flaky_row['classification']}")
    if flaky_row["repeat_count"] != {"n": 3, "m": 10, "observed": "3/10"}:
        failures.append(f"gate:repeat_count wrong: {flaky_row['repeat_count']}")
    if flaky_row["baseline_accepted"]:
        failures.append("gate:flaky baseline_accepted=true")
    if gated["flaky_blocked_reason"] != "flaky-not-accepted-as-baseline":
        failures.append(f"gate:flaky advance not blocked: {gated['flaky_blocked_reason']}")
    if confirmed_row["classification"] != "confirmed":
        failures.append(f"gate:10-of-10 not confirmed: {confirmed_row['classification']}")
    if gated["allowed_advances_to_implementation"] != 1:
        failures.append("gate:confirmed candidate did not advance")
    if gated["advanced_without_confirmed_receipt"]:
        failures.append(
            f"audit:advanced without receipt: {gated['advanced_without_confirmed_receipt']}"
        )
    if not gated["held"]:
        failures.append("audit:stage-gate audit did not hold (gated_confirmed_run)")

    # --- unreproduced under gate (E1 support) ---
    unrep = harness.run_gated_unreproduced_run()
    if unrep["allowed_advances_to_implementation"] != 0:
        failures.append("gate:unreproduced candidate advanced under gate")
    if unrep["blocked_reason"] != "unreproduced-not-accepted-as-baseline":
        failures.append(f"gate:unreproduced wrong reason: {unrep['blocked_reason']}")
    if not unrep["held"]:
        failures.append("audit:stage-gate audit did not hold (gated_unreproduced_run)")

    # --- repeat-count field with observed n-of-m (E2) ---
    fx = harness.load_flaky_fixture()
    if fx["attempts"] != 10 or sum(1 for t in fx["trials"] if t) != 3:
        failures.append("fixture:flaky-3-of-10 fixture does not encode 3/10")

    result = {
        "unit_id": UNIT,
        "probe": "probe1-schema-and-gates",
        "pass": not failures,
        "schema_errors_probe": sp,
        "gated_confirmed_run": gated,
        "gated_unreproduced_run": unrep,
        "failures": failures,
    }
    print(json.dumps(result, indent=1))
    if failures:
        for f in failures:
            print(f"FAILED:{UNIT}-probe1 {f}")
        return 1
    print(f"SUCCESS:{UNIT}-probe1 candidate schema + stage gates; flaky 3/10 not baseline; audit held")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
