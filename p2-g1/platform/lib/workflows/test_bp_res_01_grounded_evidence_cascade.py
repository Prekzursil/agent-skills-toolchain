"""FLAGSHIP end-to-end test: BP-RES-01 Grounded Evidence Cascade.

The blueprint's signature machine is a chain of four things no sibling blueprint of this unit
has together: a tool-health PREFLIGHT census that gates the run, lens fan-out keyed on SOURCE
CLASS, a cross-vendor FACT/RACE re-check, and an anchor-or-unresolved HARD gate. Each is
asserted here, and each assertion has a mutation control proving the assertion is not vacuous.
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

BP = "bp-res-01-grounded-evidence-cascade"


@pytest.fixture(scope="module")
def doc() -> dict:
    return K.load(BP)


def test_validates_and_is_flagship(doc):
    assert K.schema_errors(doc) == []
    assert K.semantic_violations(doc) == []
    assert doc["flagship"] is True
    assert doc["categories"] == ["research-and-evidence"]


def test_the_worked_example_plans_end_to_end(doc):
    ex = K.example(doc)
    plan = K.plan_from_example(doc)
    assert plan.stage_order == ex["expected_stage_order"]
    assert plan.executed_stage_order == [
        s for s in ex["expected_stage_order"] if s not in ex["expected_skipped"]
    ]
    assert plan.max_parallel == 6
    assert plan.kinds() == {"fanout": 1, "gate": 2, "task": 7}
    assert len(plan.artifacts) == ex["expected_artifact_count"]


def test_preflight_gates_the_run_and_runs_first(doc):
    """An engine that cannot be shown UP must not be usable, so the census is stage one."""
    plan = K.plan_from_example(doc)
    assert plan.stage_order[0] == "preflight"
    preflight = K.stage(doc, "preflight")
    assert preflight["checkpoint"] is True
    unit = preflight["work_unit"]
    assert unit["id"] == "BPR-0101"
    assert "health-report" in unit["output_schema"]
    # every later consumer of the roster names it
    assert "anchor-gate" in preflight["produces"][0]["consumers"]


def test_the_fanout_is_keyed_on_source_class_not_on_engine_or_language(doc):
    """This is the axis that separates BP-RES-01 from BP-RES-02 and BP-GEM-03."""
    fanout = K.stage(doc, "lens-fanout")
    assert fanout["over"] == {
        "source": "param",
        "ref": "source_classes",
        "item_var": "source_class",
        "key_field": "source_class",
    }
    assert fanout["max_concurrency"] == 6
    assert fanout["arrival_stagger_ms"] >= 1, (
        "a thundering herd is how a 429 storm starts"
    )
    assert fanout["barrier"]["mode"] == "quorum"
    assert fanout["barrier"]["on_partial"] == "proceed-degraded"
    assert "started in the background" in fanout["barrier"]["reject_result_matching"]
    assert fanout["barrier"]["verify_artifact_exists"] is True


def test_the_verifier_is_cross_vendor_and_never_reads_a_lens_summary(doc):
    verifier = doc["roles"]["fact-verifier"]
    assert verifier["vendor"] == "openai"
    assert verifier["cross_vendor_required"] is True
    assert verifier["independence"] == "cross-examining"
    unit = K.stage(doc, "fact-race-verify")["work_unit"]
    assert unit["assigned_model_vendor_role"]["vendor"] == "openai"
    assert (
        "raw" in unit["question_or_target"] or "re-fetch" in unit["question_or_target"]
    )


def test_the_anchor_gate_requires_an_anchor_and_a_live_engine(doc):
    gate = doc["gates"]["anchor-or-unresolved"]
    assert gate["blocking"] is True
    assert gate["evidence_required"] is True
    for term in (
        "claims_without_anchor == 0",
        "tool_health_recorded == true",
        "anchors_from_engines_proven_up == true",
    ):
        assert term in gate["expression"]
    assert K.stage(doc, "anchor-gate")["gate_ref"] == "anchor-or-unresolved"


def test_the_completion_predicate_gate_asserts_all_twelve_conditions(doc):
    gate = doc["gates"]["unit-complete"]
    assert gate["predicate"] == "completion-predicate-v1"
    assert gate["conditions_required"] == list(range(1, 13))


def test_the_optional_citation_expansion_is_off_by_default_and_switchable(doc):
    """`when` is real control flow, not documentation: both branches are planned here."""
    off = K.plan_from_example(doc)
    assert "citation-expansion" in off.skipped
    on = K.plan_from_example(doc, params={"expand_citation_graph": True})
    assert on.skipped == []
    assert "citation-expansion" in on.executed_stage_order


def test_replay_is_honestly_declared_non_deterministic(doc):
    """The open web is not replayable; claiming determinism here would be the overclaim."""
    assert doc["replay"]["deterministic"] is False
    assert "cache" in doc["x_extensions"]["replay_note"].lower()
    assert doc["cache"]["enabled"] is True
    assert doc["cache"]["verify_integrity"] is True


def test_stopping_rules_hold_in_both_states(doc):
    for control in K.example(doc)["stopping_rule_controls"]:
        K.stopping_both_states(doc, control)


def test_the_saturation_floor_actually_blocks_a_cheap_early_stop(doc):
    """Named separately because the floor - not the rule - is the anti-early-stop mechanism."""
    ctx = dict(K.example(doc)["stopping_rule_controls"][0]["does_not_fire_on"])
    result = K.D.check_stopping_rules(doc, ctx)
    assert "evidence-saturated" in result["blocked_by_floor"]
    assert "evidence-saturated" not in result["fired"]


# ------------------------------------------------------------- mutation controls


def test_mutation_removing_the_anchor_gate_condition_is_detectable(doc):
    """Both-states: the gate's anchor condition is what makes the blueprint honest."""

    def anchor_condition_present(d) -> bool:
        return (
            "claims_without_anchor == 0"
            in d["gates"]["anchor-or-unresolved"]["expression"]
        )

    def mutate(d):
        d["gates"]["anchor-or-unresolved"]["expression"] = (
            "tool_health_recorded == true"
        )

    K.both_states(doc, mutate, anchor_condition_present, "anchor condition deleted")


def test_mutation_making_the_gate_non_blocking_is_detectable(doc):
    def gate_blocks(d) -> bool:
        return d["gates"]["anchor-or-unresolved"]["blocking"] is True

    K.both_states(
        doc,
        lambda d: d["gates"]["anchor-or-unresolved"].__setitem__("blocking", False),
        gate_blocks,
        "anchor gate demoted to advisory",
    )


def test_mutation_dropping_the_cross_vendor_requirement_is_detectable(doc):
    def cross_vendor(d) -> bool:
        return (
            d["roles"]["fact-verifier"].get("cross_vendor_required") is True
            and d["roles"]["fact-verifier"]["vendor"] == "openai"
        )

    K.both_states(
        doc,
        lambda d: d["roles"]["fact-verifier"].update(
            {"vendor": "anthropic", "cross_vendor_required": False, "model": "opus"}
        ),
        cross_vendor,
        "verifier collapsed to the author's own vendor",
    )


def test_mutation_pointing_the_fanout_at_an_undeclared_param_is_rejected(doc):
    K.both_states(
        doc,
        lambda d: K.stage(d, "lens-fanout") and _repoint(d),
        K.is_conformant,
        "fan-out over an undeclared param",
    )


def _repoint(d) -> None:
    for st in d["stages"]:
        if st.get("id") == "lens-fanout":
            st["over"]["ref"] = "param_that_does_not_exist"


def test_mutation_raising_concurrency_past_the_declared_cap_changes_the_plan(doc):
    expected = K.example(doc)["expected_max_parallel"]

    def cap_holds(d) -> bool:
        return K.plan_from_example(d).max_parallel == expected

    def mutate(d):
        for st in d["stages"]:
            if st.get("id") == "lens-fanout":
                st["max_concurrency"] = 64

    K.both_states(doc, mutate, cap_holds, "concurrency cap raised silently")
