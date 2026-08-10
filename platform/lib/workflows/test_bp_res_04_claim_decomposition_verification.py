"""FLAGSHIP end-to-end test: BP-RES-04 Claim-Decomposition Verification Pass.

The blueprint exists to close ONE measured defect: the source implementation's validator
requires an id, a text and a recognised verdict but NOT a ``source_probe``, so a CONFIRMED claim
with no producing measurement passes with an empty violation list. Its shipped 30-test
regression misses it because that regression's missing-probe case omits the VERIFIER, not the
SOURCE.

So the central test here asserts the repaired condition is present in the gate expression AND
that removing it is detectable - the absent-source direction specifically, which is the
direction the source regression never exercised.
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

BP = "bp-res-04-claim-decomposition-verification"
REPAIRED_CONDITIONS = (
    "confirmed_claims_without_source_probe == 0",
    "refuted_claims_without_source_probe == 0",
    "same_probe_rerun_claims == 0",
    "unresolved_claims_promoted_to_confirmed == 0",
)


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
    assert plan.max_parallel == 8
    assert plan.kinds() == {"fanout": 1, "gate": 2, "task": 5}


def test_both_gate_variants_carry_all_four_repaired_conditions(doc):
    """The shadow gate must check EXACTLY as much as the blocking one; only blocking differs."""
    blocking = doc["gates"]["source-probe-required"]
    shadow = doc["gates"]["source-probe-required-shadow"]
    for gate in (blocking, shadow):
        for condition in REPAIRED_CONDITIONS:
            assert condition in gate["expression"], f"missing {condition}"
    assert blocking["expression"] == shadow["expression"], (
        "SHADOW must measure the same thing as BLOCKING - a shadow gate that checks less is a "
        "different gate wearing the same name"
    )
    assert blocking["blocking"] is True and blocking["on_fail"] == "fail"
    assert shadow["blocking"] is False and shadow["on_fail"] == "record-and-continue"


def test_mode_selects_exactly_one_gate_and_never_both(doc):
    for variant in K.example(doc)["mode_variants"]:
        plan = K.plan_from_example(doc, params={"mode": variant["mode"]})
        assert sorted(plan.skipped) == sorted(variant["expected_skipped"])
        live = [g.stage_id for g in plan.gates if not g.skipped_by_when]
        assert len(live) == 1, f"mode={variant['mode']} left {live} gates live"


def test_the_verdict_is_computed_by_a_script_not_judged_by_a_model(doc):
    runner = doc["roles"]["gate-runner"]
    assert runner["authority"] == "judge"
    assert runner["vendor"] == "any"
    unit = K.stage(doc, "emit-ledger")["work_unit"]
    assert unit["assigned_model_vendor_role"]["model"] == "none-deterministic-script"
    assert "Bash:python" in unit["tool_permissions"]
    assert doc["retry_policy"]["strategy"] == "none", (
        "retrying a deterministic reducer over unchanged inputs cannot change the result"
    )
    assert doc["retry_policy"]["max_attempts"] == 1


def test_the_mandatory_both_states_case_is_declared_on_the_reducer_unit(doc):
    """The absent-SOURCE direction must be a named required test, not an aspiration."""
    unit = K.stage(doc, "emit-ledger")["work_unit"]
    tests = " | ".join(unit["tests_required"]).lower()
    assert "empty source_probe" in tests or "empty source probe" in tests
    assert "ok=false" in tests or "violation" in tests
    assert "same-probe-rerun" in tests
    assert "violations == []" in tests, (
        "a gate that can never pass is a permanent red light; the clean-input case must be a "
        "declared test too"
    )


def test_no_claim_is_left_without_a_verdict(doc):
    """A barrier that proceeds degraded would silently drop an unverified claim."""
    fanout = K.stage(doc, "reprobe-fanout")
    assert fanout["barrier"]["mode"] == "all"
    assert fanout["barrier"]["on_partial"] == "fail"
    assert fanout["barrier"]["verify_artifact_exists"] is True


def test_an_unavailable_instrument_degrades_to_unresolved_never_to_confirmed(doc):
    unit = K.stage(doc, "reprobe-claim")["work_unit"]
    target = unit["question_or_target"].lower()
    assert "unresolved" in target
    assert "never confirmed" in target or "never" in target
    assert "instrument-unavailable" in unit["failure_classification"]


def test_the_assignment_stage_forbids_reusing_the_source_probe(doc):
    unit = K.stage(doc, "assign-instruments")["work_unit"]
    assert "same-probe-rerun" in unit["failure_classification"]
    assert "NO-INDEPENDENT-INSTRUMENT" in unit["question_or_target"]
    tests = " | ".join(unit["tests_required"])
    assert "missing instrument registry" in tests.lower()


def test_it_is_offline_and_cannot_write_outside_its_own_root(doc):
    policy = doc["tool_policy"]
    assert policy["network"] == "none"
    assert policy["source_policy"]["offline_only"] is True
    assert policy["write_paths"] == ["command-center/verification/**"]
    assert "Write(command-center/research/**)" in policy["deny"]


def test_replay_is_deterministic_because_the_gate_is_a_script(doc):
    replay = doc["replay"]
    assert replay["deterministic"] is True
    assert replay["verify"] == "hash-equal"
    assert replay["seed"] and replay["journal_path"] and replay["record"]


def test_stopping_rules_hold_in_both_states(doc):
    for control in K.example(doc)["stopping_rule_controls"]:
        K.stopping_both_states(doc, control)


# ------------------------------------------------------------- mutation controls


@pytest.mark.parametrize("condition", REPAIRED_CONDITIONS)
def test_mutation_removing_any_repaired_condition_is_detectable(doc, condition: str):
    """One control per condition - deleting any of the four must be visible."""

    def all_conditions_present(d) -> bool:
        expr = d["gates"]["source-probe-required"]["expression"]
        return all(c in expr for c in REPAIRED_CONDITIONS)

    def mutate(d):
        gate = d["gates"]["source-probe-required"]
        gate["expression"] = gate["expression"].replace(
            condition, "true_placeholder == true"
        )

    K.both_states(doc, mutate, all_conditions_present, f"deleted {condition}")


def test_mutation_letting_shadow_check_less_than_blocking_is_detectable(doc):
    def shadow_matches_blocking(d) -> bool:
        return (
            d["gates"]["source-probe-required-shadow"]["expression"]
            == d["gates"]["source-probe-required"]["expression"]
        )

    def mutate(d):
        d["gates"]["source-probe-required-shadow"]["expression"] = (
            "same_probe_rerun_claims == 0"
        )

    K.both_states(doc, mutate, shadow_matches_blocking, "shadow gate weakened")


def test_mutation_making_both_gates_run_at_once_is_detectable(doc):
    def exactly_one_gate_live(d) -> bool:
        plan = K.plan_from_example(d)
        return len([g for g in plan.gates if not g.skipped_by_when]) == 1

    def mutate(d):
        for st in d["stages"]:
            if st.get("id") == "blocking-gate":
                st.pop("when", None)

    K.both_states(
        doc, mutate, exactly_one_gate_live, "both gate variants live simultaneously"
    )


def test_mutation_softening_the_barrier_is_detectable(doc):
    def barrier_is_hard(d) -> bool:
        return K.stage(d, "reprobe-fanout")["barrier"]["on_partial"] == "fail"

    def mutate(d):
        for st in d["stages"]:
            if st.get("id") == "reprobe-fanout":
                st["barrier"]["on_partial"] = "proceed-degraded"

    K.both_states(doc, mutate, barrier_is_hard, "barrier would drop unverified claims")


def test_mutation_routing_the_reducer_to_a_model_is_detectable(doc):
    def reducer_is_a_script(d) -> bool:
        unit = K.stage(d, "emit-ledger")["work_unit"]
        return (
            unit["assigned_model_vendor_role"]["model"] == "none-deterministic-script"
        )

    def mutate(d):
        for st in d["stages"]:
            if st.get("id") == "emit-ledger":
                st["work_unit"]["assigned_model_vendor_role"]["model"] = "opus"

    K.both_states(
        doc, mutate, reducer_is_a_script, "verdict reduction handed to a model"
    )
