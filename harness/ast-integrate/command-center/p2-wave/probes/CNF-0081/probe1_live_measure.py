#!/usr/bin/env python3
"""Probe 1: re-run the live measurement and the extra-turn ledger control.

Deterministic token/cost figures must match the artifact. Wall-clock is
observational and is only required to be positive. The extra-turn plant must
increase tokens_cumulative and appear as a write the tracer sees.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import calibrate as C  # noqa: E402
import jsonschema  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0081-estimate-accuracy.json"
SCHEMA = REPO / "command-center/schema/calibration-report.schema.json"
SENTINEL = (
    "SUCCESS:CNF-0081 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every workflow has a "
    "measured counterpart or an explicit NOT-CHECKED, and the accounting "
    "source is named. Any other terminal state is FAILED:CNF-0081 "
    "<classification> with the diagnostic tail attached."
)


def close(a, b) -> bool:
    if a is None or b is None:
        return a is b
    return math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-15)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0081-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        print("FAILED:CNF-0081-probe1 completion_sentinel absent")
        return 1
    if doc.get("unit_id") != "CNF-0081":
        print("FAILED:CNF-0081-probe1 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:CNF-0081-probe1 self-declared", doc.get("state"))
        return 1

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if errs:
        print("FAILED:CNF-0081-probe1 schema", errs[0].message)
        return 1

    live = C.measure_all()
    extra = live["extra_turn_control"]
    print(
        json.dumps(
            {
                "extra_turn": extra,
                "n_measured_live": live["aggregates"]["n_measured"],
                "n_not_checked_live": live["aggregates"]["n_not_checked"],
                "mape_cost_live": live["aggregates"]["mape_cost_pct"],
                "bias_live": live["aggregates"]["bias_direction"],
                "oom_live": live["aggregates"]["order_of_magnitude_overruns"],
            },
            sort_keys=True,
        )
    )
    if not extra["ok"]:
        print("FAILED:CNF-0081-probe1 extra-turn control")
        return 1

    art_rows = {r["id"]: r for r in doc["rows"]}
    live_rows = {r["id"]: r for r in live["rows"]}
    if set(art_rows) != set(live_rows):
        print("FAILED:CNF-0081-probe1 row id set mismatch")
        print(" only artifact", sorted(set(art_rows) - set(live_rows))[:8])
        print(" only live", sorted(set(live_rows) - set(art_rows))[:8])
        return 1

    for rid, arow in art_rows.items():
        lrow = live_rows[rid]
        if arow.get("status") != lrow.get("status"):
            print(f"FAILED:CNF-0081-probe1 status {rid}")
            return 1
        if not arow.get("accounting_source"):
            print(f"FAILED:CNF-0081-probe1 unnamed accounting {rid}")
            return 1
        if arow["status"] == "NOT-CHECKED":
            if arow.get("error") not in (None, {}):
                if arow.get("error"):
                    print(f"FAILED:CNF-0081-probe1 NOT-CHECKED has error {rid}")
                    return 1
            continue
        aobs = arow["observed"]
        lobs = lrow["observed"]
        if aobs["tokens_cumulative"] != lobs["tokens_cumulative"]:
            print(f"FAILED:CNF-0081-probe1 tokens {rid}")
            return 1
        if aobs["tokens_last_turn"] != lobs["tokens_last_turn"]:
            print(f"FAILED:CNF-0081-probe1 last_turn {rid}")
            return 1
        if not close(aobs["cost_usd"], lobs["cost_usd"]):
            print(f"FAILED:CNF-0081-probe1 cost {rid}")
            return 1
        if not (lobs["wall_clock_s"] > 0):
            print(f"FAILED:CNF-0081-probe1 non-positive wall_clock {rid}")
            return 1
        if aobs["tokens_cumulative"] == aobs["tokens_last_turn"] and aobs["n_turns"] > 1:
            print(f"FAILED:CNF-0081-probe1 cumulative conflated with last-turn {rid}")
            return 1

    aagg = doc["aggregates"]
    lagg = live["aggregates"]
    if aagg["bias_direction"] != lagg["bias_direction"]:
        print("FAILED:CNF-0081-probe1 bias_direction mismatch")
        return 1
    if not close(aagg["mape_cost_pct"], lagg["mape_cost_pct"]):
        print("FAILED:CNF-0081-probe1 mape_cost mismatch")
        return 1
    if aagg["order_of_magnitude_overruns"] != lagg["order_of_magnitude_overruns"]:
        print("FAILED:CNF-0081-probe1 oom mismatch")
        return 1
    if aagg["n_not_checked"] != lagg["n_not_checked"]:
        print("FAILED:CNF-0081-probe1 n_not_checked mismatch")
        return 1
    if aagg.get("estimator_biased_low") != (aagg["bias_direction"] == "LOW"):
        print("FAILED:CNF-0081-probe1 biased_low inconsistent with direction")
        return 1

    print(
        "typed_ok=True extra_turn=True mape="
        f"{aagg['mape_cost_pct']} bias={aagg['bias_direction']} "
        f"oom={aagg['order_of_magnitude_overruns']}"
    )
    print("SUCCESS:CNF-0081-probe1 live measure and extra-turn control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
