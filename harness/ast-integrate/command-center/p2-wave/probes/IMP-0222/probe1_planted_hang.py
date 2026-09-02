#!/usr/bin/env python3
"""Named probe 1: planted hang in a 50-unit cohort.

Both-states, counted from IsolatedPipelineRunner's ledger:
  clean — 50/50 COMPLETED, zero TIMEOUT, detector silent
  hang  — 49 COMPLETED, hung unit TIMEOUT/timeout-typed (not absent)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from scenario import (  # noqa: E402
    COHORT_N,
    HANG_ID,
    SENTINEL,
    TIMEOUT,
    TIMEOUT_TYPED,
    load_receipt,
    run_isolated,
    summarize,
)


def main() -> int:
    try:
        doc = load_receipt()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAILED:IMP-0222-probe1 receipt {exc}")
        return 1

    clean = run_isolated(hang=False)
    hung = run_isolated(hang=True)
    sc = summarize(clean)
    sh = summarize(hung)

    problems: list[str] = []
    if sc["n"] != COHORT_N or sc["completed"] != COHORT_N:
        problems.append(f"clean completed={sc['completed']}/{sc['n']} want={COHORT_N}/{COHORT_N}")
    if sc["timeout"] != 0 or sc["timeout_typed"] != 0:
        problems.append(f"clean detector fired timeout={sc['timeout']} typed={sc['timeout_typed']}")
    if sc["pipeline_ids"] != COHORT_N:
        problems.append(f"clean pipeline_ids={sc['pipeline_ids']} want={COHORT_N}")

    if sh["n"] != COHORT_N:
        problems.append(f"hang n={sh['n']}")
    if sh["completed"] != COHORT_N - 1:
        problems.append(f"hang completed={sh['completed']} want={COHORT_N - 1}")
    if sh["timeout"] != 1 or sh["timeout_typed"] != 1:
        problems.append(
            f"hang timeout={sh['timeout']} typed={sh['timeout_typed']} want 1 timeout-typed"
        )
    if sh["timeout_untyped"] != 0:
        problems.append("hang timeout present but not timeout-typed")
    if sh["absent"] != 0:
        problems.append("hang ledger has absent rows")
    if HANG_ID not in sh["timeout_unit_ids"]:
        problems.append(f"hung id {HANG_ID} not timeout-typed; got {sh['timeout_unit_ids']}")
    if HANG_ID in sh["completed_unit_ids"]:
        problems.append(f"hung id {HANG_ID} mis-recorded COMPLETED")

    hung_row = hung.by_id().get(HANG_ID)
    if hung_row is None:
        problems.append(f"hung id {HANG_ID} ABSENT from ledger")
    else:
        if hung_row.terminal_state != TIMEOUT or hung_row.timeout_class != TIMEOUT_TYPED:
            problems.append(
                f"hung row state={hung_row.terminal_state} class={hung_row.timeout_class}"
            )
        if hung_row.note == "ABSENT-terminal-record":
            problems.append("hung row is absent-placeholder, not a real timeout")

    detector_clean = sc["timeout"] > 0
    detector_hang = sh["timeout_typed"] == 1 and sh["completed"] == COHORT_N - 1
    if detector_clean or not detector_hang:
        problems.append(
            f"both-states failed silent_on_clean={not detector_clean} fire_on_hang={detector_hang}"
        )

    payload = {
        "unit_id": "IMP-0222",
        "probe": "probe1-planted-hang",
        "pass": not problems,
        "clean": {
            k: sc[k] for k in ("n", "completed", "timeout", "timeout_typed", "barrier_wait_s")
        },
        "hang": {
            k: sh[k]
            for k in (
                "n",
                "completed",
                "timeout",
                "timeout_typed",
                "timeout_unit_ids",
                "barrier_wait_s",
            )
        },
        "receipt_state": doc.get("state"),
        "sentinel_in_receipt": SENTINEL in json.dumps(doc),
        "problems": problems,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"clean {sc['completed']}/{sc['n']} timeout={sc['timeout']} "
        f"hang {sh['completed']}/{sh['n']} timeout_typed={sh['timeout_typed']} "
        f"hung={sh['timeout_unit_ids']}"
    )
    if problems:
        for p in problems:
            print(f"FAILED:IMP-0222-probe1 {p}")
        return 1
    print("SUCCESS:IMP-0222-probe1 planted hang 49/50 + timeout-typed; clean 50/50 silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
