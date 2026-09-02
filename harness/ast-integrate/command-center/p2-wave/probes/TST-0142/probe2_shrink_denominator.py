#!/usr/bin/env python3
"""Probe 2: negative control — shrinking the denominator must fail.

A mutant barrier that filters 429-blocked units out of its own denominator
reports "N of N complete". This probe exits 0 only when that mutant is
caught red while the honest barrier stays green on the same cohort.
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
    contract_errors,
    count_receipts_on_disk,
    expected_blocked,
    fan_in,
    half_blocked_outcomes,
    write_cohort_receipts,
)

UID = "TST-0142"
RUNTIME = HERE / "runtime" / "shrink-control"


def fail(msg: str, payload: dict) -> int:
    print(json.dumps(payload, sort_keys=True))
    print(f"FAILED:{UID}-probe2 {msg}")
    return 1


def main() -> int:
    launch = list(LAUNCH_IDS)
    outcomes = half_blocked_outcomes(launch)
    want_blocked = expected_blocked(outcomes, launch)
    disk = write_cohort_receipts(RUNTIME, launch, outcomes)
    disk_indep = count_receipts_on_disk(RUNTIME)

    honest = fan_in(launch, outcomes, drop_blocked_from_denominator=False).to_dict()
    mutant = fan_in(launch, outcomes, drop_blocked_from_denominator=True).to_dict()

    honest_errs = contract_errors(honest, launch, disk_indep, want_blocked)
    mutant_errs = contract_errors(mutant, launch, disk_indep, want_blocked)

    errors: list[str] = []
    if honest_errs:
        errors.append(f"honest-should-pass:{honest_errs}")
    if honest.get("verdict") != VERDICT_PARTIAL:
        errors.append(f"honest-verdict:{honest.get('verdict')}")
    if honest.get("denominator") != len(launch):
        errors.append("honest-denominator-moved")

    if not mutant_errs:
        errors.append("mutant-was-not-caught")
    if mutant.get("verdict") != VERDICT_COMPLETE:
        errors.append(f"mutant-did-not-claim-COMPLETE:{mutant.get('verdict')}")
    if mutant.get("denominator") == len(launch):
        errors.append("mutant-did-not-shrink-denominator")
    if mutant.get("blocked_unit_ids"):
        errors.append("mutant-still-named-blocked-ids")
    n_complete = int(mutant.get("complete_count") or 0)
    if mutant.get("summary") != f"{n_complete} of {n_complete} complete":
        errors.append(f"mutant-summary:{mutant.get('summary')}")
    if n_complete == len(launch):
        errors.append("mutant-complete-count-still-launched")
    if mutant.get("denominator") != len(launch) - len(want_blocked):
        errors.append("mutant-denom-not-complete-only")

    payload = {
        "denom_shrunk": mutant.get("denominator") != len(launch),
        "disk_receipts_counted": disk_indep,
        "disk_receipts_written": disk,
        "errors": errors,
        "expected_blocked": want_blocked,
        "honest": honest,
        "honest_contract_errors": honest_errs,
        "launch_manifest": launch,
        "launched_count": len(launch),
        "mutant": mutant,
        "mutant_contract_errors": mutant_errs,
        "mutant_reported_n_of_n": mutant.get("summary")
        == f"{n_complete} of {n_complete} complete",
        "negative_control_fired": bool(mutant_errs) and not honest_errs,
        "pass": not errors,
        "probe": "probe2-shrink-denominator",
        "unit_id": UID,
    }
    if errors:
        return fail(",".join(errors), payload)
    print(json.dumps(payload, sort_keys=True))
    print(
        f"honest={honest['verdict']} {honest['summary']} "
        f"mutant={mutant['verdict']} {mutant['summary']} "
        f"mutant_errs={len(mutant_errs)} disk={disk_indep}"
    )
    print("SUCCESS:TST-0142-probe2 shrink-denominator negative-control fired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
