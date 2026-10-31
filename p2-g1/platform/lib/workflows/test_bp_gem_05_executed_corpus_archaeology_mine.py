"""FLAGSHIP end-to-end test: BP-GEM-05 Executed-Corpus Archaeology Mine.

Two properties carry the blueprint and both get mutation controls:

1. ZERO LLM in the classification path. Handing a byte / line / set-membership comparison to
   model judgement measured 86% accurate with 100% of the errors pointing at data loss, so every
   classifying stage is pinned to a script and only the "does this MATTER" stage gets a model.
2. TWO mechanically different enumeration probes must corroborate, AND a probe known to
   enumerate a DIFFERENT population must be rejected - that rejection is what proves the
   corroboration check can discriminate at all rather than rubber-stamping any two numbers.
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

BP = "bp-gem-05-executed-corpus-archaeology-mine"
SCRIPT_ONLY_STAGES = (
    "enumerate-probe-a",
    "enumerate-probe-b",
    "corroboration-check",
    "resolve-existence",
    "mechanism-scan",
    "snapshot-survivors",
    "recover-dead-ledgers",
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
    assert plan.kinds() == {"gate": 2, "task": 8}
    assert plan.max_parallel == 1


def test_the_two_enumeration_probes_are_independent_and_run_before_anything_else(doc):
    plan = K.plan_from_example(doc)
    assert plan.stage_order[:2] == ["enumerate-probe-a", "enumerate-probe-b"]
    a = K.stage(doc, "enumerate-probe-a")
    b = K.stage(doc, "enumerate-probe-b")
    assert a.get("depends_on") in (None, []), "probe A must not wait on anything"
    assert b.get("depends_on") in (None, []), "probe B must not depend on probe A"
    assert a["role"] != b["role"], (
        "the same role running both probes is one signal, not two"
    )
    assert "different MECHANISM" in b["work_unit"]["tests_required"][
        1
    ] or "different MECHANISM" in " | ".join(b["work_unit"]["tests_required"])


def test_the_wrong_population_probe_must_be_rejected_not_averaged(doc):
    """This is the detector control: a check that cannot discriminate measures nothing."""
    assert doc["params"]["wrong_population_probe"]["required"] is True
    unit = K.stage(doc, "enumerate-probe-b")["work_unit"]
    tests = " | ".join(unit["tests_required"])
    assert "REJECTED" in tests and "averaged in" in tests
    check = K.stage(doc, "corroboration-check")["work_unit"]
    assert "must never enter the disagreement arithmetic" in " | ".join(
        check["tests_required"]
    )
    gate = doc["gates"]["probes-corroborate"]
    assert "wrong_population_probe_rejected == true" in gate["expression"]


def test_the_corroboration_gate_blocks_the_index_and_forbids_llm_classification(doc):
    gate = doc["gates"]["probes-corroborate"]
    assert gate["blocking"] is True
    assert gate["on_fail"] == "fail"
    assert "enumeration_probes_agree == true" in gate["expression"]
    assert "llm_calls_in_classification_path == 0" in gate["expression"]
    plan = K.plan_from_example(doc)
    order = plan.stage_order
    assert order.index("corroboration-gate") < order.index("resolve-existence")
    assert order.index("corroboration-gate") < order.index("mechanism-scan")


def test_no_model_appears_anywhere_in_the_classification_path(doc):
    for stage_id in SCRIPT_ONLY_STAGES:
        unit = K.stage(doc, stage_id)["work_unit"]
        assert (
            unit["assigned_model_vendor_role"]["model"] == "none-deterministic-script"
        ), stage_id
    interpreter = K.stage(doc, "interpret-topologies")["work_unit"]
    assert interpreter["assigned_model_vendor_role"]["model"] == "opus"
    assert doc["model_routing"]["default"]["model"] == "none-deterministic-script"
    assert doc["roles"]["topology-interpreter"]["speaking_rights"] == "on-request"


def test_the_interpreter_may_not_reclassify_what_the_script_decided(doc):
    unit = K.stage(doc, "interpret-topologies")["work_unit"]
    assert "Do not re-classify mechanisms" in unit["question_or_target"]
    tests = " | ".join(unit["tests_required"])
    assert "script's classification wins over the model's reading" in tests


def test_a_missing_script_is_a_first_class_outcome(doc):
    unit = K.stage(doc, "resolve-existence")["work_unit"]
    assert "FIRST-CLASS OUTCOME" in unit["question_or_target"]
    tests = " | ".join(unit["tests_required"])
    assert "never dropped from the index" in tests
    assert "must equal the record count exactly" in tests


def test_the_snapshot_carries_a_byte_parity_check(doc):
    unit = K.stage(doc, "snapshot-survivors")["work_unit"]
    assert "byte-parity-report" in unit["output_schema"]
    assert "hash on both sides" in unit["evidence_requirement"]
    tests = " | ".join(unit["tests_required"])
    assert "truncated copy" in tests, (
        "a snapshot without a parity check can hold truncated copies"
    )


def test_the_optional_ledger_recovery_joins_on_the_id_not_the_content_hash(doc):
    recovery = K.stage(doc, "recover-dead-ledgers")
    assert recovery["when"] == "recover_dead_run_ledgers == true"
    unit = recovery["work_unit"]
    assert "content hash, not a label" in unit["question_or_target"]
    assert "was NOT used as the join field" in unit["evidence_requirement"]
    plan = K.plan_from_example(doc)
    assert "recover-dead-ledgers" in plan.skipped
    on = K.plan_from_example(doc, params={"recover_dead_run_ledgers": True})
    assert on.skipped == []


def test_it_is_fully_deterministic_offline_and_never_egresses_the_index(doc):
    assert doc["replay"]["deterministic"] is True
    assert doc["replay"]["verify"] == "hash-equal"
    assert doc["retry_policy"]["strategy"] == "none"
    assert doc["tool_policy"]["network"] == "none"
    assert doc["tool_policy"]["source_policy"]["offline_only"] is True
    assert "never egressed" in doc["estimate"]["impact"]["blast_radius"]


def test_stopping_rules_hold_in_both_states(doc):
    for control in K.example(doc)["stopping_rule_controls"]:
        K.stopping_both_states(doc, control)


# ------------------------------------------------------------- mutation controls


@pytest.mark.parametrize("stage_id", SCRIPT_ONLY_STAGES)
def test_mutation_putting_a_model_in_the_classification_path_is_detectable(
    doc, stage_id: str
):
    def classification_is_mechanical(d) -> bool:
        return all(
            K.stage(d, sid)["work_unit"]["assigned_model_vendor_role"]["model"]
            == "none-deterministic-script"
            for sid in SCRIPT_ONLY_STAGES
        )

    def mutate(d):
        for st in d["stages"]:
            if st.get("id") == stage_id:
                st["work_unit"]["assigned_model_vendor_role"]["model"] = "opus"

    K.both_states(
        doc, mutate, classification_is_mechanical, f"{stage_id} handed to a model"
    )


def test_mutation_collapsing_the_two_probes_into_one_is_detectable(doc):
    def two_independent_probes(d) -> bool:
        a = K.stage(d, "enumerate-probe-a")
        b = K.stage(d, "enumerate-probe-b")
        return a["role"] != b["role"] and not b.get("depends_on")

    def mutate(d):
        for st in d["stages"]:
            if st.get("id") == "enumerate-probe-b":
                st["role"] = "mechanical-indexer"
                st["depends_on"] = ["enumerate-probe-a"]

    K.both_states(
        doc, mutate, two_independent_probes, "probe B became a re-run of probe A"
    )


def test_mutation_dropping_the_wrong_population_rejection_is_detectable(doc):
    def rejection_required(d) -> bool:
        return (
            "wrong_population_probe_rejected == true"
            in d["gates"]["probes-corroborate"]["expression"]
        )

    K.both_states(
        doc,
        lambda d: d["gates"]["probes-corroborate"].__setitem__(
            "expression",
            "enumeration_probes_agree == true AND llm_calls_in_classification_path == 0",
        ),
        rejection_required,
        "the detector control was removed from the gate",
    )


def test_mutation_letting_the_index_proceed_on_disagreeing_probes_is_detectable(doc):
    def gate_blocks(d) -> bool:
        gate = d["gates"]["probes-corroborate"]
        return gate["blocking"] is True and gate["on_fail"] == "fail"

    K.both_states(
        doc,
        lambda d: d["gates"]["probes-corroborate"].update(
            {"blocking": False, "on_fail": "record-and-continue"}
        ),
        gate_blocks,
        "disagreeing probes would no longer block the index",
    )


def test_mutation_making_the_wrong_population_param_optional_is_detectable(doc):
    def control_is_required(d) -> bool:
        spec = d["params"]["wrong_population_probe"]
        return spec.get("required") is True and "default" not in spec

    def mutate(d):
        spec = d["params"]["wrong_population_probe"]
        spec.pop("required", None)
        spec["default"] = ""

    K.both_states(
        doc, mutate, control_is_required, "the detector control became optional"
    )
