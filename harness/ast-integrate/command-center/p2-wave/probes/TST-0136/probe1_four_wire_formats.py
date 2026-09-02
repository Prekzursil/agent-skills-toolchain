#!/usr/bin/env python3
"""Probe 1: four wire formats + both-states ignore-Retry-After control.

Honor client must pass delta-seconds, HTTP-date, past date (immediate),
and malformed (fallback, no crash). Ignore client must fail all four.
Live HTTP plus FakeClock. Production dispatch_scheduled is also driven
with string headers.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from harness import (  # noqa: E402
    honor_criteria,
    reconcile,
    result_to_dict,
    run_four_cases,
    run_scheduler_four,
)


def fail(msg: str) -> int:
    print(f"FAILED:TST-0136-probe1 {msg}")
    return 1


def main() -> int:
    fake_honor = run_four_cases(live=False, honor=True)
    fake_ignore = run_four_cases(live=False, honor=False)
    live_honor = run_four_cases(live=True, honor=True)
    live_ignore = run_four_cases(live=True, honor=False)
    scheduled = run_scheduler_four()

    if len(fake_honor) != 4 or len(fake_ignore) != 4:
        return fail("expected four fake cases")
    if len(live_honor) != 4 or len(live_ignore) != 4:
        return fail("expected four live cases")

    honor_fail = [r.case_id for r in fake_honor if not honor_criteria(r)]
    ignore_pass = [r.case_id for r in fake_ignore if honor_criteria(r)]
    if honor_fail:
        return fail(f"honor FakeClock failed {honor_fail}")
    if ignore_pass:
        return fail(f"ignore FakeClock passed honor criteria {ignore_pass}")

    live_honor_fail = [r.case_id for r in live_honor if not honor_criteria(r)]
    live_ignore_pass = [r.case_id for r in live_ignore if honor_criteria(r)]
    if live_honor_fail:
        return fail(f"honor live HTTP failed {live_honor_fail}")
    if live_ignore_pass:
        return fail(f"ignore live HTTP passed honor criteria {live_ignore_pass}")

    sched_fail = [s["id"] for s in scheduled if not s["ok"]]
    if sched_fail:
        return fail(f"dispatch_scheduled string headers failed {sched_fail}")

    rec_fake = reconcile(fake_honor, live=False)
    rec_live = reconcile(live_honor, live=True)
    if not rec_fake["ok"]:
        return fail(f"fake clock reconciliation {rec_fake}")
    if not rec_live["ok"]:
        return fail(f"live clock reconciliation {rec_live}")

    crashed = [r.case_id for r in fake_honor + live_honor if r.crashed]
    if crashed:
        return fail(f"honor client crashed {crashed}")

    payload = {
        "probe": "probe1-four-wire-formats",
        "unit_id": "TST-0136",
        "fake_honor": [result_to_dict(r) for r in fake_honor],
        "fake_ignore": [result_to_dict(r) for r in fake_ignore],
        "live_honor": [result_to_dict(r) for r in live_honor],
        "live_ignore": [result_to_dict(r) for r in live_ignore],
        "dispatch_scheduled": scheduled,
        "reconcile_fake": rec_fake,
        "reconcile_live": rec_live,
        "both_states": {
            "honor_passes_all_four": honor_fail == [] and live_honor_fail == [],
            "ignore_fails_all_four": ignore_pass == [] and live_ignore_pass == [],
        },
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "honor FakeClock+live HTTP pass four wire formats; "
        "ignore client fails all four; clocks reconciled"
    )
    print("SUCCESS:TST-0136-probe1 four wire formats both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
