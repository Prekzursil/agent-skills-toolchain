#!/usr/bin/env python3
"""Probe 2: independent re-run of the 40-unit hung batch plus null-tolerant fan-in.

A null result from one unit must not poison the barrier for the rest. The
poisoning fan-in mutation must raise BarrierPoison on the same fixture.
The hung batch is re-run with a different hung index than probe 1.
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
HUNG_INDEX = 0
NULL_INDEX = 7
TIMEOUT_S = 0.4


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0452-probe2 {msg}")
    return 1


def main() -> int:
    P.reset_hang_gate()
    try:
        hung = P.run_per_unit(
            P.build_hung_batch(
                batch_size=BATCH,
                hung_index=HUNG_INDEX,
                timeout_s=TIMEOUT_S,
                prefix="R",
            )
        )
    finally:
        P.release_hung_workers()

    null_specs = P.build_null_batch(
        batch_size=BATCH, null_index=NULL_INDEX, timeout_s=TIMEOUT_S
    )
    tolerant = P.run_per_unit(null_specs)
    poison_raised = False
    poison_msg = ""
    try:
        P.poisoning_fan_in(list(_results_from_report(tolerant)))
    except P.BarrierPoison as exc:
        poison_raised = True
        poison_msg = str(exc)

    print(json.dumps(P.report_to_dict(hung), sort_keys=True))
    print(json.dumps(P.report_to_dict(tolerant), sort_keys=True))
    print(f"poison_raised={poison_raised}")

    non_stalled = hung.success + hung.failed + hung.nulls
    if non_stalled != 39 or hung.stalled != 1 or hung.deadlock:
        return fail(
            f"reviewer hung-batch counts {non_stalled}+{hung.stalled} deadlock={hung.deadlock}"
        )
    hung_id = f"R-{HUNG_INDEX:02d}"
    if not any(s["unit_id"] == hung_id and s["state"] == "STALLED" for s in hung.slots):
        return fail(f"reviewer hung unit {hung_id} not STALLED")

    if tolerant.nulls != 1 or tolerant.success != 39:
        return fail(
            f"null fan-in success={tolerant.success} nulls={tolerant.nulls} want 39+1"
        )
    if tolerant.poisoned or tolerant.deadlock or tolerant.stalled != 0:
        return fail("null slot stalled or poisoned the cohort")
    if tolerant.terminal != BATCH:
        return fail("null-tolerant fan-in dropped a slot")
    null_id = f"N-{NULL_INDEX:02d}"
    null_slots = [s for s in tolerant.slots if s["unit_id"] == null_id]
    if len(null_slots) != 1 or null_slots[0]["state"] != "NULL":
        return fail(f"null unit {null_id} not classified NULL: {null_slots}")
    sibling_failed = [
        s
        for s in tolerant.slots
        if s["unit_id"] != null_id and s["state"] != "SUCCESS"
    ]
    if sibling_failed:
        return fail(f"null poisoned siblings: {sibling_failed[:4]}")
    if not poison_raised:
        return fail("poisoning fan-in mutation did not raise on a null slot")
    if "null-poisons-barrier" not in poison_msg:
        return fail(f"poison mutation message missing class: {poison_msg}")

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
    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS":
        return fail("reviewer verdict not PASS")
    if reviewer.get("independent") is not True:
        return fail("reviewer not independent")

    print(
        f"reviewer_hung 39+1 hung={hung_id} survivors_complete_s={hung.survivors_complete_s}"
    )
    print(
        f"null_fanin success=39 nulls=1 poison_mutation_raised={poison_raised}"
    )
    print("SUCCESS:IMP-0452-probe2 null-tolerant fan-in and reviewer hung-batch")
    return 0


def _results_from_report(report: P.FanInReport) -> list[P.UnitResult]:
    """Rebuild UnitResult values so the poisoning mutation sees the same None slot."""
    out: list[P.UnitResult] = []
    for slot in report.slots:
        value = None if slot["value_is_null"] else {"ok": True}
        out.append(
            P.UnitResult(
                unit_id=slot["unit_id"],
                state=slot["state"],
                value=value,
                started_at=0.0,
                ended_at=slot["elapsed_s"],
                elapsed_s=slot["elapsed_s"],
                error=slot.get("error"),
            )
        )
    return out


if __name__ == "__main__":
    raise SystemExit(main())
