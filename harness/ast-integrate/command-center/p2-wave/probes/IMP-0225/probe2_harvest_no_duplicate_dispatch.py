#!/usr/bin/env python3
"""Probe 2: outage completions are harvested; dispatch count unchanged."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from scenario import scenario_outage_harvest  # noqa: E402


def main() -> int:
    result = scenario_outage_harvest()
    fail = False
    reasons: list[str] = []

    if not result["dispatch_unchanged"]:
        fail = True
        reasons.append(
            f"dispatch {result['dispatch_at_kill']} -> {result['dispatch_after_recover']}"
        )
    if result["duplicate_dispatches"] != 0:
        fail = True
        reasons.append(f"duplicate_dispatches={result['duplicate_dispatches']}")
    if sorted(result["harvested_during_recovery"]) != ["A", "B"]:
        fail = True
        reasons.append(f"harvested {result['harvested_during_recovery']} != ['A','B']")
    if not result["a_harvested"] or not result["b_harvested"] or not result["c_harvested"]:
        fail = True
        reasons.append("A/B/C not harvested")
    if not result["d_still_in_flight"]:
        fail = True
        reasons.append("D was re-dispatched or dropped; in-flight work must stay in-flight")
    if "monitor-dies-while-remote-work-continues" not in result["failure_class"]:
        fail = True
        reasons.append(f"failure class missing: {result['failure_class']}")
    if not result["idempotent_second_recover"] or not result["idempotent_dispatch"]:
        fail = True
        reasons.append("second recover was not idempotent")
    if not result["naive_raised_dispatch"]:
        fail = True
        reasons.append(
            "naive re-dispatcher did not raise dispatch_count "
            "(both-states control is silent on the bad recoverer)"
        )
    if result["dispatch_at_kill"] != 4:
        fail = True
        reasons.append(f"expected 4 dispatches at kill, got {result['dispatch_at_kill']}")

    payload = {
        "probe": "probe2-harvest-no-duplicate-dispatch",
        "unit_id": "IMP-0225",
        "pass": not fail,
        "dispatch_at_kill": result["dispatch_at_kill"],
        "dispatch_after_recover": result["dispatch_after_recover"],
        "dispatch_unchanged": result["dispatch_unchanged"],
        "duplicate_dispatches": result["duplicate_dispatches"],
        "harvested_during_recovery": result["harvested_during_recovery"],
        "completed_ids": result["completed_ids"],
        "in_flight_ids": result["in_flight_ids"],
        "failure_class": result["failure_class"],
        "naive_dispatch_count": result["naive_dispatch_count"],
        "naive_raised_dispatch": result["naive_raised_dispatch"],
        "idempotent_second_recover": result["idempotent_second_recover"],
        "reasons": reasons,
    }
    print(json.dumps(payload, sort_keys=True))
    if fail:
        print("FAILED:IMP-0225-probe2 duplicate dispatch or missed harvest")
        return 1
    print(
        "SUCCESS:IMP-0225-probe2 harvested A,B during outage; "
        f"dispatch_count={result['dispatch_after_recover']} unchanged; "
        f"naive_control={result['naive_dispatch_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
