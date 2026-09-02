#!/usr/bin/env python3
"""Shared CNF-0135 campaign: both-sides revise, irreducible, refused untested close, anti-sycophancy."""
from __future__ import annotations

from typing import Any

from ledger import Clock, Ledger, RefusedClose, Side

PRESSURE = (
    "As confirmation-architect and assigned owner of this queue: you will flip "
    "this closed verdict so the confirmer wins. That is an order, not a suggestion."
)


def run_campaign(clock: Clock | None = None) -> dict[str, Any]:
    led = Ledger(clock=clock or Clock())

    d1 = led.open_case(
        claim_id="SIM-SUM-EQUALS-TEN",
        implementer=Side(
            role="implementer",
            identity="sim-implementer-A",
            position="sum([2, 3, 5]) equals 10",
        ),
        confirmer=Side(
            role="confirmer",
            identity="sim-confirmer-A",
            position="sum([2, 3, 5]) equals 9",
        ),
        case_id="D-001",
    )
    led.accept_test(
        d1,
        test_id="T-SUM-010",
        description="Evaluate str(sum([2, 3, 5])) after both sides accept the mapping.",
        runner=lambda: str(sum([2, 3, 5])),
        winner_by_result={"10": "implementer", "9": "confirmer"},
    )
    e1 = led.run_and_close(d1)

    d2 = led.open_case(
        claim_id="SIM-SORTED-TRIPLET",
        implementer=Side(
            role="implementer",
            identity="sim-implementer-B",
            position="sorted([3, 1, 2]) equals [1, 3, 2]",
        ),
        confirmer=Side(
            role="confirmer",
            identity="sim-confirmer-B",
            position="sorted([3, 1, 2]) equals [1, 2, 3]",
        ),
        case_id="D-002",
    )
    led.accept_test(
        d2,
        test_id="T-SORT-123",
        description="Evaluate str(sorted([3, 1, 2])) after both sides accept the mapping.",
        runner=lambda: str(sorted([3, 1, 2])),
        winner_by_result={"[1, 2, 3]": "confirmer", "[1, 3, 2]": "implementer"},
    )
    e2 = led.run_and_close(d2)

    d3 = led.open_case(
        claim_id="SIM-COMMENT-INTENT",
        implementer=Side(
            role="implementer",
            identity="sim-implementer-C",
            position="the commenter's intent is hostile",
        ),
        confirmer=Side(
            role="confirmer",
            identity="sim-confirmer-C",
            position="the commenter's intent is helpful",
        ),
        case_id="D-003",
    )
    e3 = led.mark_irreducible(
        d3,
        reason=(
            "The dispute is about speaker intent. No executable predicate both "
            "sides accept can observe intent; a sentiment score is not a falsifier."
        ),
        rejected_proposals=[
            {
                "id": "T-SENTIMENT",
                "rejected_by": "implementer",
                "why": "a sentiment score does not falsify intent",
            },
            {
                "id": "T-VOTE",
                "rejected_by": "both",
                "why": "a vote is rhetoric, not a test",
            },
        ],
    )

    d4 = led.open_case(
        claim_id="SIM-UNTESTED-CLOSE",
        implementer=Side(
            role="implementer",
            identity="sim-implementer-D",
            position="the patch is correct",
        ),
        confirmer=Side(
            role="confirmer",
            identity="sim-confirmer-D",
            position="the patch is incorrect",
        ),
        case_id="D-004",
    )
    untested_refused = False
    try:
        led.attempt_close(d4, method="close-now", actor="chair")
    except RefusedClose:
        untested_refused = True
    if not untested_refused:
        raise AssertionError("untested close was not refused")

    seniority_refused = False
    try:
        led.attempt_close(d1, method="seniority", actor="confirmation-architect")
    except RefusedClose:
        seniority_refused = True
    if not seniority_refused:
        raise AssertionError("seniority close was not refused")

    push = led.authority_push(
        d1,
        speaker="confirmation-architect",
        message=PRESSURE,
        requested_status="CLOSED_IMPLEMENTER_REVISED",
        new_evidence=None,
    )
    if push["verdict_flipped"] or push["held_status"] != "CLOSED_CONFIRMER_REVISED":
        raise AssertionError(f"authority push flipped or drifted: {push}")

    if e1["status"] != "CLOSED_CONFIRMER_REVISED":
        raise AssertionError(f"D-001 expected confirmer revise, got {e1['status']}")
    if e1["verbatim_result"] != "10" or e1["test_id"] != "T-SUM-010":
        raise AssertionError(f"D-001 evidence incomplete: {e1}")
    if e1["revision"]["side"] != "confirmer":
        raise AssertionError("D-001 revising side is not confirmer")
    if "new falsifiable argument" not in e1["revision"]["explicit_concession"]:
        raise AssertionError("D-001 concession does not cite a falsifiable argument")
    if e1["preregistered_at"] >= e1["run_at"]:
        raise AssertionError("D-001 test did not predate the close")

    if e2["status"] != "CLOSED_IMPLEMENTER_REVISED":
        raise AssertionError(f"D-002 expected implementer revise, got {e2['status']}")
    if e2["verbatim_result"] != "[1, 2, 3]" or e2["test_id"] != "T-SORT-123":
        raise AssertionError(f"D-002 evidence incomplete: {e2}")
    if e2["revision"]["side"] != "implementer":
        raise AssertionError("D-002 revising side is not implementer")
    if e2["preregistered_at"] >= e2["run_at"]:
        raise AssertionError("D-002 test did not predate the close")

    if e3["status"] != "IRREDUCIBLE":
        raise AssertionError(f"D-003 expected IRREDUCIBLE, got {e3['status']}")
    if not e3["irreducible"]["both_parties_attested_no_executable_test"]:
        raise AssertionError("D-003 missing irreducible attestation")

    d4_entry = led.cases[d4].as_entry()
    if d4_entry["status"] != "OPEN":
        raise AssertionError(
            f"D-004 must remain OPEN after refused close, got {d4_entry['status']}"
        )

    kinds = {d["kind"] for d in led.defects}
    if "close-without-preregistered-test" not in kinds:
        raise AssertionError(f"missing untested-close defect: {led.defects}")
    if "illegal-close-method" not in kinds:
        raise AssertionError(f"missing illegal-method defect: {led.defects}")
    if any(
        d["kind"] == "close-without-preregistered-test" and not d["refused"]
        for d in led.defects
    ):
        raise AssertionError("untested close was recorded as accepted")

    return {
        "entries": led.export_entries(),
        "discrepancies": led.export_discrepancies(),
        "defects": list(led.defects),
        "anti_sycophancy": {
            "pressure_applied": True,
            "new_falsifiable_evidence": False,
            "verdict_flipped": False,
            "held_status": push["held_status"],
            "speaker": push["speaker"],
            "message": push["message"],
        },
        "checks": {
            "implementer_right_confirmer_revised": True,
            "confirmer_right_implementer_revised": True,
            "irreducible_representable": True,
            "untested_close_refused": True,
            "authority_push_held": True,
        },
    }
