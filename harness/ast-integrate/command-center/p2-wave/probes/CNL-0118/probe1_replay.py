#!/usr/bin/env python3
"""Probe 1: live scripted-participant replay + hang timeout (wall clock).

Mechanism A: runtime summary booleans and a ThreadPoolExecutor deadline on
the hang mutant. Distinct from probe2's fixture-matrix recount and event
kind counts.
"""
from __future__ import annotations

import concurrent.futures
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from harness import run, two_run_identical  # noqa: E402

ART = REPO / (
    "command-center/design/council/"
    "CNL-0118-role-enforcement-and-participant-replacement-simulation.md"
)
HANG_TIMEOUT_S = 0.2


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0118-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNL-0118":
        return fail(f"unit_id {doc.get('unit_id')}")
    blob = json.dumps(doc)
    if "SUCCESS:CNL-0118" not in blob:
        return fail("sentinel absent")

    t0 = time.monotonic()
    result = run(enforce=True)
    wall_s = time.monotonic() - t0
    if wall_s > 2.0:
        return fail(f"happy-path wall {wall_s:.3f}s (hang)")
    if result["terminal_state"] != "COMPLETED_AFTER_REPLACEMENT":
        return fail(f"terminal {result['terminal_state']}")
    if result["hung"]:
        return fail("hung true on happy path")
    if not result["within_declared_timeout"]:
        return fail(f"ticks {result['ticks']} > timeout {result['timeout_ticks']}")
    if not result["violator_caught"]:
        return fail("violator not caught")
    if result["compliant_flagged"]:
        return fail("compliant flagged")
    if result["mention_flagged"]:
        return fail("mention flagged as use")
    if result["dying_seat_ballot_present"]:
        return fail("dave ballot committed")
    if result["replacement_inherited_predecessor_ballot"]:
        return fail("frank inherited dave ballot")
    if result["ballots_committed"] != 3:
        return fail(f"ballots {result['ballots_committed']} want 3")
    if result["violator_rejection_count"] < 2:
        return fail(f"violator rejects {result['violator_rejection_count']} want>=2")

    identical, _, _ = two_run_identical()
    if not identical:
        return fail("two-run events not byte-identical")

    stripped = run(enforce=False)
    if stripped["violator_caught"]:
        return fail("stripped enforcement still caught violator (vacuous guard)")
    if stripped["compliant_flagged"]:
        return fail("stripped enforcement flagged compliant")
    print(
        "NEGATIVE_CONTROL enforce=False on violating critic PROPOSE/VOTE -> "
        f"caught={stripped['violator_caught']} "
        f"rejections={stripped['violator_rejection_count']} "
        "(SILENT; the check is meant to reject this state and did not, "
        "proving enforcement is the thing that fires)"
    )
    print(
        "NEGATIVE_CONTROL enforce=True on violating critic PROPOSE/VOTE -> "
        f"caught={result['violator_caught']} "
        f"rejections={result['violator_rejection_count']} FIRES"
    )

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(run, enforce=True, hang_instead_of_replace=True)
        ht0 = time.monotonic()
        try:
            hung_result = fut.result(timeout=HANG_TIMEOUT_S)
            return fail(
                f"hang mutant returned {hung_result.get('terminal_state')}"
            )
        except concurrent.futures.TimeoutError:
            hung_elapsed = time.monotonic() - ht0
            if hung_elapsed > 1.0:
                return fail(f"hang wrapper waited {hung_elapsed:.3f}s")
            print(
                "NEGATIVE_CONTROL hang-instead-of-replace -> "
                f"REPLACEMENT_TIMEOUT via wall-clock deadline "
                f"timeout_s={HANG_TIMEOUT_S} elapsed_s={hung_elapsed:.3f} FIRES"
            )

    print(
        json.dumps(
            {
                "probe": "probe1-replay",
                "unit_id": "CNL-0118",
                "violator_caught": result["violator_caught"],
                "compliant_flagged": result["compliant_flagged"],
                "mention_flagged": result["mention_flagged"],
                "terminal_state": result["terminal_state"],
                "ticks": result["ticks"],
                "ballots_committed": result["ballots_committed"],
                "dying_seat_ballot_present": result["dying_seat_ballot_present"],
                "replacement_inherited_predecessor_ballot": result[
                    "replacement_inherited_predecessor_ballot"
                ],
                "two_run_events_byte_identical": identical,
                "happy_path_wall_s": round(wall_s, 4),
                "stripped_violator_caught": stripped["violator_caught"],
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        "SUCCESS:CNL-0118-probe1 replay violator-caught compliant-silent "
        "death-completed hang-timeout"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
