#!/usr/bin/env python3
"""Probe 1: hung-unit-in-batch.

With one unit hung forever in a 40-unit batch, the other 39 must still reach a
terminal state under the per-unit pipeline. The phase-wide barrier mutation
must deadlock (watchdog expires with the hung unit still PENDING, never STALLED).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import pipeline as P  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0452.json"
SENTINEL = "SENTINEL:IMP-0452:PIPELINE-NO-COHORT-DEADLOCK"
BATCH = 40
HUNG_INDEX = 17
TIMEOUT_S = 0.4
BARRIER_WATCHDOG_S = 0.12


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0452-probe1 {msg}")
    return 1


def main() -> int:
    P.reset_hang_gate()
    try:
        specs = P.build_hung_batch(
            batch_size=BATCH, hung_index=HUNG_INDEX, timeout_s=TIMEOUT_S
        )
        good = P.run_per_unit(specs)
        P.release_hung_workers()
        P.reset_hang_gate()
        bad = P.run_phase_barrier(
            P.build_hung_batch(
                batch_size=BATCH, hung_index=HUNG_INDEX, timeout_s=TIMEOUT_S
            ),
            watchdog_s=BARRIER_WATCHDOG_S,
        )
    finally:
        P.release_hung_workers()

    print(json.dumps(P.report_to_dict(good), sort_keys=True))
    print(json.dumps(P.report_to_dict(bad), sort_keys=True))

    non_stalled = good.success + good.failed + good.nulls
    if good.slot_count != BATCH:
        return fail(f"slot_count={good.slot_count} want {BATCH}")
    if non_stalled != 39 or good.stalled != 1:
        return fail(
            f"counts terminal_non_stalled={non_stalled} stalled={good.stalled} "
            "want 39+1"
        )
    if good.deadlock or good.poisoned or good.pending != 0:
        return fail("per-unit cohort deadlock or poison")
    if good.hung_classified_s is None:
        return fail("hung unit never classified STALLED")
    if good.survivors_complete_s >= good.hung_classified_s:
        return fail(
            f"survivors waited for hung sibling "
            f"({good.survivors_complete_s} >= {good.hung_classified_s})"
        )
    if good.survivors_complete_s >= TIMEOUT_S * 0.8:
        return fail(
            f"39-unit wall clock {good.survivors_complete_s}s looks like a barrier wait"
        )
    if good.hung_classified_s < TIMEOUT_S * 0.5:
        return fail("STALLED classification arrived before the per-unit timeout")
    hung_id = f"U-{HUNG_INDEX:02d}"
    hung_slots = [s for s in good.slots if s["unit_id"] == hung_id]
    if len(hung_slots) != 1 or hung_slots[0]["state"] != "STALLED":
        return fail(f"hung unit {hung_id} not STALLED: {hung_slots}")
    if not P.shutdown_source_refuses_join():
        return fail("run_per_unit joins hung workers (shutdown wait=True)")

    if not bad.deadlock or bad.pending < 1:
        return fail(
            f"phase-barrier mutation did not deadlock pending={bad.pending} "
            f"deadlock={bad.deadlock}"
        )
    if bad.stalled != 0:
        return fail("phase-barrier classified STALLED; the defect is it never does")
    if bad.terminal >= BATCH:
        return fail("phase-barrier harvested the hung unit as terminal")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel absent")
    counts = (doc.get("report") or {}).get("hung_batch") or {}
    if int(counts.get("terminal_non_stalled") or 0) != 39:
        return fail("receipt hung_batch.terminal_non_stalled != 39")
    if int(counts.get("stalled") or 0) != 1:
        return fail("receipt hung_batch.stalled != 1")

    print(
        f"per_unit 39+1 survivors_complete_s={good.survivors_complete_s} "
        f"hung_classified_s={good.hung_classified_s}"
    )
    print(
        f"phase_barrier deadlock={bad.deadlock} pending={bad.pending} "
        f"terminal={bad.terminal}"
    )
    print("SUCCESS:IMP-0452-probe1 hung-unit-in-batch 39-terminal + 1-STALLED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
