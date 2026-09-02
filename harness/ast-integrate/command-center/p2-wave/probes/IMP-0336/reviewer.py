"""Independent reviewer for IMP-0336: re-derive silent-drop from the public API.

Does not import author narrative. Starts from the harvested ledger and the
action-plan rows, recomputes carry_into_action_plan, then applies the mutant.
"""
from __future__ import annotations

from council.protocol.premortem import (
    FAILED_PREMISE,
    Acceptance,
    ActionPlan,
    CauseStatement,
    Mitigation,
    RecordingKernel,
    carry_into_action_plan,
    drop_mode_silently,
    harvest,
    omitted_unmitigated,
)

# Local copies of the fixture values so the reviewer does not start from
# scenario.py's pass/fail helpers (those are the author's summary of the test).
_STATEMENTS = (
    CauseStatement(
        participant="alice",
        cause="Kernel bypass lets a topology write participant output without a turn event",
        likelihood=4,
        detectability=4,
    ),
    CauseStatement(
        participant="bob",
        cause="Action-plan generator emits an action the council never agreed to",
        likelihood=3,
        detectability=3,
    ),
    CauseStatement(
        participant="cara",
        cause="Premortem ledger is harvested then dropped before any mitigation is bound",
        likelihood=5,
        detectability=5,
    ),
    CauseStatement(
        participant="dan",
        cause="Outer observer ring is cost-only and never cited in the decision",
        likelihood=2,
        detectability=2,
    ),
)


def _plan() -> ActionPlan:
    return ActionPlan(
        plan_id="plan-ship-council-kernel",
        decision_id="decision-premortem-carry",
        mitigations=(
            Mitigation(
                id="ACT-001",
                mitigates="FM-001",
                owner="kernel-owner",
                precondition="kernel records turns",
                verification="event-count invariant",
                mechanism="KernelTurnSink required",
                sequence=1,
            ),
            Mitigation(
                id="ACT-002",
                mitigates="FM-002",
                owner="outcomes-owner",
                precondition="mitigation cites ledger id",
                verification="orphan-mitigation refused",
                mechanism="schema check",
                sequence=2,
            ),
            Mitigation(
                id="ACT-003",
                mitigates="FM-003",
                owner="protocol-owner",
                precondition="bind before publish",
                verification="traceability count",
                mechanism="invariant",
                sequence=3,
            ),
        ),
        acceptances=(
            Acceptance(
                failure_mode_id="FM-004",
                owner="chair",
                rationale="Observer-ring cost is accepted and published, not omitted.",
            ),
        ),
    )


def review_silent_drop() -> dict:
    ledger = harvest(
        plan_id="plan-ship-council-kernel",
        premise=FAILED_PREMISE,
        statements=_STATEMENTS,
        kernel=RecordingKernel(),
    )
    good = carry_into_action_plan(ledger, _plan())
    bad = carry_into_action_plan(ledger, drop_mode_silently(_plan(), "FM-003"))
    omitted = omitted_unmitigated(bad, [])
    count_falls = bad.traceability_count < good.traceability_count
    invariant_fires = (not bad.invariant_ok) and good.invariant_ok
    listed = "FM-003" in bad.unmitigated_ids
    verdict = (
        "PASS"
        if count_falls and invariant_fires and listed and omitted
        else "FAIL"
    )
    return {
        "reviewer_id": "IMP-0336-reviewer-silent-drop",
        "independent": True,
        "fresh_context": True,
        "starts_from": "tests/public-api",
        "good_count": good.traceability_count,
        "bad_count": bad.traceability_count,
        "count_falls": count_falls,
        "invariant_fires": invariant_fires,
        "dropped_listed_explicitly": listed,
        "omit_empty_report_detected": bool(omitted),
        "verdict": verdict,
        "pass": verdict == "PASS",
    }
