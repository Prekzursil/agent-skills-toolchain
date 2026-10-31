"""FLAGSHIP end-to-end test: BP-RES-05 Briefed-Fact Re-Probe Council.

Three properties are load-bearing and each gets a mutation control:

1. a re-probe must be MECHANISM-different from the brief's own probe, enforced by a gate that
   REJECTS and re-assigns rather than warning;
2. a split verdict is resolved by reading probes, never by counting agents (the measured
   baseline: 4 agents refuted a false fact while 2 "CONFIRMED" it by re-running the
   orchestrator's own broken probe);
3. the pipeline ends in a HARD BARRIER, so the fan-out this gate protects cannot start early.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
for _p in (str(HERE.parent), str(HERE)):
    if _p not in sys.path:  # pragma: no cover - import plumbing
        sys.path.insert(0, _p)

import bp1_testkit as K  # noqa: E402

BP = "bp-res-05-briefed-fact-reprobe-council"


@pytest.fixture(scope="module")
def doc() -> dict:
    return K.load(BP)


def test_validates_and_is_flagship(doc):
    assert K.schema_errors(doc) == []
    assert K.semantic_violations(doc) == []
    assert doc["flagship"] is True


def test_the_worked_example_plans_end_to_end(doc):
    ex = K.example(doc)
    plan = K.plan_from_example(doc)
    assert plan.stage_order == ex["expected_stage_order"]
    assert plan.max_parallel == 6
    assert plan.kinds() == {
        "barrier": 1,
        "fanout": 1,
        "gate": 2,
        "human_checkpoint": 1,
        "task": 6,
    }


def test_the_independence_gate_rejects_and_reassigns_rather_than_warning(doc):
    gate = doc["gates"]["mechanism-independence"]
    assert "reprobes_sharing_mechanism_with_original == 0" in gate["expression"]
    assert "facts_without_assigned_instrument == 0" in gate["expression"]
    assert gate["blocking"] is True
    assert gate["on_fail"] == "retry", (
        "a shared-mechanism re-probe must be RE-ASSIGNED; recording and continuing would ship "
        "the very evidence-tag theatre this blueprint exists to stop"
    )


def test_the_reprober_is_told_the_original_probe_and_forbidden_from_rerunning_it(doc):
    role = doc["roles"]["reprober"]
    assert "FORBIDDEN" in role["description"]
    assert role["independence"] == "independent"
    unit = K.stage(doc, "reprobe-fact")["work_unit"]
    assert "same-probe-rerun" in unit["failure_classification"]
    target = unit["question_or_target"]
    assert "does NOT count" in target or "does not count" in target
    tests = " | ".join(unit["tests_required"])
    assert "PROBE refuted" in tests and "FACT confirmed" in tests, (
        "the probe and the fact are separate verdicts; a broken probe must not refute a true fact"
    )


def test_reconciliation_reads_probes_and_a_vote_count_is_invalid(doc):
    reconciler = doc["roles"]["reconciler"]
    assert reconciler["authority"] == "judge"
    assert "never by counting agents" in reconciler["description"]
    unit = K.stage(doc, "reconcile-by-probe")["work_unit"]
    assert "more specific probe wins" in unit["question_or_target"]
    assert "vote count is invalid" in unit["evidence_requirement"]
    tests = " | ".join(unit["tests_required"])
    assert "4-refute / 2-confirm" in tests, (
        "the measured baseline must be a declared test case"
    )


def test_a_zero_correction_result_triggers_an_audit_instead_of_a_green_light(doc):
    """A perfect brief is less likely than a broken council: four briefed facts were false once."""
    audit = K.stage(doc, "zero-correction-audit")
    assert audit["when"] == "corrections_found == 0"
    unit = audit["work_unit"]
    assert "FALSE version" in unit["evidence_requirement"]
    tests = " | ".join(unit["tests_required"])
    assert "KNOWN-FALSE" in tests
    assert "measuring nothing" in tests


def test_the_audit_and_the_owner_checkpoint_are_mutually_exclusive_by_fact(doc):
    for variant in K.example(doc)["fact_variants"]:
        plan = K.plan_from_example(doc, facts=variant["facts"])
        assert sorted(plan.skipped) == sorted(variant["expected_skipped"])


def test_the_hard_barrier_precedes_any_downstream_fanout(doc):
    plan = K.plan_from_example(doc)
    barrier = K.stage(doc, "launch-barrier")
    assert barrier["barrier"]["mode"] == "all"
    assert barrier["barrier"]["on_partial"] == "fail"
    assert set(barrier["barrier"]["require_stages"]) == {
        "reconcile-by-probe",
        "corrections-gate",
    }
    order = plan.stage_order
    assert order.index("launch-barrier") > order.index("reconcile-by-probe")
    assert order.index("launch-barrier") > order.index("corrections-gate")
    assert order.index("launch-barrier") < order.index("owner-accept")


def test_the_owner_checkpoint_cannot_hang(doc):
    checkpoint = K.stage(doc, "owner-accept")
    assert checkpoint["on_timeout"] == "escalate"
    assert checkpoint["timeout_seconds"] >= 3600
    assert checkpoint["approval_mode"] == "owner-only"
    assert len(checkpoint["options"]) >= 2
    assert checkpoint["decision_artifact"]["path"].endswith("owner-decision.json")


def test_it_is_cheap_relative_to_the_fanout_it_protects(doc):
    """The whole argument for a serial pre-barrier is that it costs one short agent per fact."""
    est = doc["estimate"]
    assert est["wallclock_seconds"]["expected"] <= 1200
    assert est["tokens"]["expected"] <= 200000
    assert doc["params"]["planned_fanout_size"]["required"] is True


def test_stopping_rules_hold_in_both_states(doc):
    for control in K.example(doc)["stopping_rule_controls"]:
        K.stopping_both_states(doc, control)


# ------------------------------------------------------------- mutation controls


def test_mutation_softening_the_independence_gate_is_detectable(doc):
    def gate_rejects(d) -> bool:
        gate = d["gates"]["mechanism-independence"]
        return gate["on_fail"] == "retry" and gate["blocking"] is True

    K.both_states(
        doc,
        lambda d: d["gates"]["mechanism-independence"].update(
            {"on_fail": "record-and-continue", "blocking": False}
        ),
        gate_rejects,
        "shared-mechanism re-probes would be recorded and accepted",
    )


def test_mutation_removing_the_zero_correction_audit_is_detectable(doc):
    def audit_present(d) -> bool:
        return any(st.get("id") == "zero-correction-audit" for st in d["stages"])

    def mutate(d):
        d["stages"] = [
            st for st in d["stages"] if st.get("id") != "zero-correction-audit"
        ]
        for st in d["stages"]:
            st["depends_on"] = [
                x for x in st.get("depends_on", []) if x != "zero-correction-audit"
            ]
        barrier = next(st for st in d["stages"] if st.get("id") == "launch-barrier")
        barrier["joins"] = [j for j in barrier["joins"] if j != "zero-correction-audit"]

    K.both_states(doc, mutate, audit_present, "zero-correction audit deleted")


def test_mutation_letting_the_barrier_proceed_degraded_is_detectable(doc):
    def barrier_is_hard(d) -> bool:
        return K.stage(d, "launch-barrier")["barrier"]["on_partial"] == "fail"

    def mutate(d):
        for st in d["stages"]:
            if st.get("id") == "launch-barrier":
                st["barrier"]["on_partial"] = "proceed-degraded"

    K.both_states(
        doc, mutate, barrier_is_hard, "fan-out could start on an uncorrected brief"
    )


def test_mutation_moving_the_barrier_after_the_owner_checkpoint_is_detectable(doc):
    def barrier_before_owner(d) -> bool:
        try:
            order = K.plan_from_example(d).stage_order
        except K.D.PlanError:
            return False
        return order.index("launch-barrier") < order.index("owner-accept")

    def mutate(d):
        for st in d["stages"]:
            if st.get("id") == "launch-barrier":
                st["depends_on"] = ["owner-accept"]
            if st.get("id") == "owner-accept":
                st["depends_on"] = ["corrections-gate"]

    K.both_states(
        doc, mutate, barrier_before_owner, "barrier moved after the owner checkpoint"
    )


def test_mutation_giving_the_reconciler_a_vote_count_mandate_is_detectable(doc):
    def reads_probes(d) -> bool:
        unit = K.stage(d, "reconcile-by-probe")["work_unit"]
        return "more specific probe wins" in unit["question_or_target"]

    def mutate(d):
        for st in d["stages"]:
            if st.get("id") == "reconcile-by-probe":
                st["work_unit"]["question_or_target"] = (
                    "Rule on each fact by majority vote across the re-probers."
                )

    K.both_states(doc, mutate, reads_probes, "reconciliation reduced to a vote count")
