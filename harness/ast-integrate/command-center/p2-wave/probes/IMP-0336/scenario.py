"""IMP-0336 fixtures: known-good harvest and both-states silent-drop mutant."""
from __future__ import annotations

import ast
from pathlib import Path

from council.protocol.premortem import (
    FAILED_PREMISE,
    Acceptance,
    ActionPlan,
    CauseStatement,
    KernelBypass,
    Mitigation,
    PremiseMissing,
    RecordingKernel,
    SchemaInvalid,
    carry_into_action_plan,
    drop_mode_silently,
    harvest,
    omitted_unmitigated,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PREMORTEM_PY = REPO / "tools/council/protocol/premortem.py"

PLAN_ID = "plan-ship-council-kernel"
DECISION_ID = "decision-premortem-carry"

STATEMENTS = (
    CauseStatement(
        participant="alice",
        cause="Kernel bypass lets a topology write participant output without a turn event",
        likelihood=4,
        detectability=4,
        evidence="IMP-0264 falsifiable question: bypass path",
    ),
    CauseStatement(
        participant="bob",
        cause="Action-plan generator emits an action the council never agreed to",
        likelihood=3,
        detectability=3,
        evidence="IMP-0340 falsifiable question: unagreed action",
    ),
    CauseStatement(
        participant="cara",
        cause="Premortem ledger is harvested then dropped before any mitigation is bound",
        likelihood=5,
        detectability=5,
        evidence="IMP-0336 collected-and-dropped failure mode",
    ),
    CauseStatement(
        participant="dan",
        cause="Outer observer ring is cost-only and never cited in the decision",
        likelihood=2,
        detectability=2,
        evidence="IMP-0335 observer contribution near zero",
    ),
)

# Carry three modes into the plan; accept the low-RPN observer-cost row explicitly.
GOOD_MITIGATIONS = (
    Mitigation(
        id="ACT-001",
        mitigates="FM-001",
        owner="kernel-owner",
        precondition="KernelTurnSink is the only writer of participant output",
        verification="turns_recorded == turns_executed and call-graph check fires on bypass",
        mechanism="Refuse harvest when kernel is None; record every cause as a turn",
        sequence=1,
    ),
    Mitigation(
        id="ACT-002",
        mitigates="FM-002",
        owner="outcomes-owner",
        precondition="Every mitigation cites a ledger id",
        verification="orphan-mitigation is schema-invalid",
        mechanism="carry_into_action_plan rejects mitigates not in the ledger",
        sequence=2,
    ),
    Mitigation(
        id="ACT-003",
        mitigates="FM-003",
        owner="protocol-owner",
        precondition="bind() runs before the action plan is published",
        verification="traceability_count equals mitigated ledger rows; silent drop FALLS",
        mechanism="Invariant: every ledger row is mitigated or explicitly accepted",
        sequence=3,
    ),
)

GOOD_ACCEPTANCES = (
    Acceptance(
        failure_mode_id="FM-004",
        owner="chair",
        rationale=(
            "Observer-ring cost is accepted for this plan: measured contribution "
            "may be near zero and is published rather than tuned (IMP-0335)."
        ),
    ),
)

SILENT_DROP_TARGET = "FM-003"


def good_harvest(kernel: RecordingKernel | None = None):
    sink = kernel if kernel is not None else RecordingKernel()
    ledger = harvest(
        plan_id=PLAN_ID,
        premise=FAILED_PREMISE,
        statements=STATEMENTS,
        kernel=sink,
    )
    return ledger, sink


def good_plan() -> ActionPlan:
    return ActionPlan(
        plan_id=PLAN_ID,
        decision_id=DECISION_ID,
        mitigations=GOOD_MITIGATIONS,
        acceptances=GOOD_ACCEPTANCES,
    )


def evaluate_harvest() -> dict:
    ledger, sink = good_harvest()
    entries = [row.to_dict() for row in ledger.entries]
    schema_ok = all(
        isinstance(row["likelihood"], int)
        and isinstance(row["detectability"], int)
        and 1 <= row["likelihood"] <= 5
        and 1 <= row["detectability"] <= 5
        and row["rpn"] == row["likelihood"] * row["detectability"]
        and row["id"].startswith("FM-")
        and row["cause"]
        and row["participant"]
        for row in entries
    )
    premise_refused = False
    try:
        harvest(
            plan_id=PLAN_ID,
            premise="the plan might work",
            statements=STATEMENTS,
            kernel=RecordingKernel(),
        )
    except PremiseMissing:
        premise_refused = True
    likelihood_refused = False
    try:
        harvest(
            plan_id=PLAN_ID,
            premise=FAILED_PREMISE,
            statements=[
                {
                    "participant": "eve",
                    "cause": "Scores were written as prose instead of ints",
                    "likelihood": "high",
                    "detectability": 3,
                }
            ],
            kernel=RecordingKernel(),
        )
    except SchemaInvalid as exc:
        likelihood_refused = "likelihood-not-int" in str(exc)
    kernel_bypass_refused = False
    try:
        harvest(
            plan_id=PLAN_ID,
            premise=FAILED_PREMISE,
            statements=STATEMENTS,
            kernel=None,
        )
    except KernelBypass:
        kernel_bypass_refused = True
    empty_refused = False
    try:
        harvest(
            plan_id=PLAN_ID,
            premise=FAILED_PREMISE,
            statements=[],
            kernel=RecordingKernel(),
        )
    except SchemaInvalid as exc:
        empty_refused = "empty-harvest" in str(exc)
    expected_turns = 1 + len(STATEMENTS)
    return {
        "entry_count": len(entries),
        "schema_ok": schema_ok,
        "premise_refused": premise_refused,
        "likelihood_refused": likelihood_refused,
        "kernel_bypass_refused": kernel_bypass_refused,
        "empty_refused": empty_refused,
        "turns_recorded": sink.turns_recorded,
        "turns_executed": sink.turns_executed,
        "event_count_ok": sink.turns_recorded == expected_turns
        and sink.turns_recorded == sink.turns_executed,
        "entries": entries,
        "pass": bool(
            schema_ok
            and len(entries) == 4
            and premise_refused
            and likelihood_refused
            and kernel_bypass_refused
            and empty_refused
            and sink.turns_recorded == expected_turns
        ),
    }


def evaluate_invariant() -> dict:
    ledger, _sink = good_harvest()
    trace = carry_into_action_plan(ledger, good_plan())
    every_mode_closed = all(
        d["disposition"] in {"mitigated", "accepted"} for d in trace.dispositions
    )
    return {
        "traceability_count": trace.traceability_count,
        "mitigated_ids": list(trace.mitigated_ids),
        "accepted_ids": list(trace.accepted_ids),
        "unmitigated_ids": list(trace.unmitigated_ids),
        "silent_drop_ids": list(trace.silent_drop_ids),
        "invariant_ok": trace.invariant_ok,
        "every_mode_closed": every_mode_closed,
        "unmitigated_listed_explicitly": list(trace.unmitigated_ids) == ["FM-004"],
        "pass": bool(
            trace.invariant_ok
            and trace.traceability_count == 3
            and list(trace.unmitigated_ids) == ["FM-004"]
            and list(trace.accepted_ids) == ["FM-004"]
            and not trace.silent_drop_ids
            and every_mode_closed
        ),
    }


def evaluate_silent_drop() -> dict:
    ledger, _sink = good_harvest()
    good = carry_into_action_plan(ledger, good_plan())
    mutant_plan = drop_mode_silently(good_plan(), SILENT_DROP_TARGET)
    bad = carry_into_action_plan(ledger, mutant_plan)
    count_falls = bad.traceability_count < good.traceability_count
    omitted = omitted_unmitigated(bad, claimed_unmitigated=[])
    listed = omitted_unmitigated(bad, claimed_unmitigated=list(bad.unmitigated_ids))
    return {
        "good_count": good.traceability_count,
        "bad_count": bad.traceability_count,
        "count_falls": count_falls,
        "good_invariant_ok": good.invariant_ok,
        "bad_invariant_ok": bad.invariant_ok,
        "dropped_id": SILENT_DROP_TARGET,
        "bad_unmitigated_ids": list(bad.unmitigated_ids),
        "dropped_listed": SILENT_DROP_TARGET in bad.unmitigated_ids
        and SILENT_DROP_TARGET in bad.silent_drop_ids,
        "omit_report_detected": omitted == list(bad.unmitigated_ids),
        "full_report_omits_nothing": listed == [],
        "both_states": bool(good.invariant_ok and (not bad.invariant_ok) and count_falls),
        "pass": bool(
            count_falls
            and good.traceability_count == 3
            and bad.traceability_count == 2
            and good.invariant_ok
            and not bad.invariant_ok
            and SILENT_DROP_TARGET in bad.unmitigated_ids
            and SILENT_DROP_TARGET in bad.silent_drop_ids
            and omitted == list(bad.unmitigated_ids)
            and listed == []
        ),
    }


def protocol_writes_participant_output() -> bool:
    """True when premortem.py opens a write handle — a kernel bypass smell."""
    tree = ast.parse(PREMORTEM_PY.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open":
            for arg in node.args[1:]:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    if any(flag in arg.value for flag in ("w", "a", "x", "+")):
                        return True
            for kw in node.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    val = str(kw.value.value)
                    if any(flag in val for flag in ("w", "a", "x", "+")):
                        return True
    return False
