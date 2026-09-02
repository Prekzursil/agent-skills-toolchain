#!/usr/bin/env python3
"""Probe 1: both-states control for 429 partial fan-in.

Half the cohort 429-blocked => typed PARTIAL naming every blocked id,
denominator frozen at the launched count.

The unblocked cohort => COMPLETE with the same denominator.

Evidence: (a) barrier return vs launch manifest, (b) independent count of
receipt files on disk.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from fanin_barrier import (  # noqa: E402
    LAUNCH_IDS,
    VERDICT_COMPLETE,
    VERDICT_PARTIAL,
    all_complete_outcomes,
    contract_errors,
    count_receipts_on_disk,
    expected_blocked,
    expected_complete,
    fan_in,
    half_blocked_outcomes,
    write_cohort_receipts,
)

UID = "TST-0142"
RUNTIME = HERE / "runtime"


def fail(msg: str, payload: dict) -> int:
    print(json.dumps(payload, sort_keys=True))
    print(f"FAILED:{UID}-probe1 {msg}")
    return 1


def main() -> int:
    launch = list(LAUNCH_IDS)
    errors: list[str] = []

    blocked_dir = RUNTIME / "half-blocked"
    blocked_outcomes = half_blocked_outcomes(launch)
    disk_blocked = write_cohort_receipts(blocked_dir, launch, blocked_outcomes)
    disk_blocked_indep = count_receipts_on_disk(blocked_dir)
    want_blocked = expected_blocked(blocked_outcomes, launch)
    want_complete = expected_complete(blocked_outcomes, launch)
    blocked_result = fan_in(launch, blocked_outcomes).to_dict()
    blocked_errs = contract_errors(
        blocked_result, launch, disk_blocked_indep, want_blocked
    )
    errors.extend(f"half-blocked:{e}" for e in blocked_errs)
    if len(want_blocked) * 2 != len(launch):
        errors.append("fixture-not-half-blocked")
    if blocked_result.get("verdict") != VERDICT_PARTIAL:
        errors.append(f"half-blocked-verdict:{blocked_result.get('verdict')}")
    if blocked_result.get("denominator") != len(launch):
        errors.append("half-blocked-denominator-moved")
    if blocked_result.get("summary") == f"{len(want_complete)} of {len(want_complete)} complete":
        errors.append("half-blocked-reported-n-of-n-after-drop")
    if disk_blocked != disk_blocked_indep:
        errors.append("half-blocked-disk-count-desynced")

    free_dir = RUNTIME / "unblocked"
    free_outcomes = all_complete_outcomes(launch)
    disk_free = write_cohort_receipts(free_dir, launch, free_outcomes)
    disk_free_indep = count_receipts_on_disk(free_dir)
    free_result = fan_in(launch, free_outcomes).to_dict()
    free_errs = contract_errors(free_result, launch, disk_free_indep, [])
    errors.extend(f"unblocked:{e}" for e in free_errs)
    if free_result.get("verdict") != VERDICT_COMPLETE:
        errors.append(f"unblocked-verdict:{free_result.get('verdict')}")
    if free_result.get("denominator") != blocked_result.get("denominator"):
        errors.append("denominator-not-shared-across-states")
    if free_result.get("denominator") != len(launch):
        errors.append("unblocked-denominator-moved")
    if disk_free != len(launch):
        errors.append("unblocked-disk-count")

    payload = {
        "errors": errors,
        "half_blocked": {
            "disk_receipts_counted": disk_blocked_indep,
            "disk_receipts_written": disk_blocked,
            "evidence_a_roster_equals_manifest": blocked_result.get("roster") == launch,
            "evidence_b_disk_count_equals_launched": disk_blocked_indep == len(launch),
            "expected_blocked": want_blocked,
            "expected_complete": want_complete,
            "result": blocked_result,
        },
        "launch_manifest": launch,
        "launched_count": len(launch),
        "pass": not errors,
        "probe": "probe1-partial-both-states",
        "same_denominator": (
            blocked_result.get("denominator")
            == free_result.get("denominator")
            == len(launch)
        ),
        "unit_id": UID,
        "unblocked": {
            "disk_receipts_counted": disk_free_indep,
            "disk_receipts_written": disk_free,
            "evidence_a_roster_equals_manifest": free_result.get("roster") == launch,
            "evidence_b_disk_count_equals_launched": disk_free_indep == len(launch),
            "result": free_result,
        },
    }
    if errors:
        return fail(",".join(errors), payload)
    print(json.dumps(payload, sort_keys=True))
    print(
        f"PARTIAL {blocked_result['summary']} blocked={want_blocked} "
        f"COMPLETE {free_result['summary']} denom={len(launch)} "
        f"disk={disk_blocked_indep}/{disk_free_indep}"
    )
    print("SUCCESS:TST-0142-probe1 both-states typed-PARTIAL frozen-denominator")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
