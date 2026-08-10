"""FLAGSHIP end-to-end test: BP-GEM-02 Anti-Overfit Candidate Gate.

The signature property is FAIL-CLOSED on a blank required input: with an empty already-built
inventory the gate must REFUSE, because passing every candidate when the dedup set is missing is
the fail-open this blueprint exists to prevent (a required-but-blank field defaults to worst
case, not to "probably fine").

Second property: it may JUDGE but never SEARCH. Its tool policy denies every discovery tool, so
it cannot quietly turn into a second sweep - which is what would make it a duplicate of BP-GEM-01.
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

BP = "bp-gem-02-anti-overfit-candidate-gate"
DISCOVERY_TOOLS = (
    "WebSearch",
    "WebFetch",
    "mcp__search-hub__web_search_exa",
    "mcp__searxng__searxng_web_search",
    "mcp__github__search_repositories",
    "mcp__codex__codex",
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
    assert plan.max_parallel == 1, (
        "judgement is serial by design; nothing here fans out"
    )
    assert plan.kinds() == {"gate": 2, "task": 6}


def test_the_fail_closed_gate_is_the_very_first_stage(doc):
    """A completeness check that runs after the work has already been judged is decoration."""
    plan = K.plan_from_example(doc)
    assert plan.stage_order[0] == "input-completeness-gate"
    gate = doc["gates"]["inputs-complete"]
    for condition in (
        "already_built_inventory_rows > 0",
        "rejected_components_declared > 0",
        "absorption_budget_declared == true",
        "candidate_rows > 0",
    ):
        assert condition in gate["expression"]
    assert gate["blocking"] is True
    assert gate["on_fail"] == "fail"


def test_a_blank_inventory_makes_the_refusal_rule_fire(doc):
    """The declared control, asserted directly: blank input escalates, populated input does not."""
    control = next(
        c
        for c in K.example(doc)["stopping_rule_controls"]
        if c["rule"] == "refuse-on-blank-input"
    )
    K.stopping_both_states(doc, control)
    fires = K.D.check_stopping_rules(doc, control["fires_on"])
    row = next(r for r in fires["rules"] if r["id"] == "refuse-on-blank-input")
    assert row["on_stop"] == "escalate", (
        "a blank required input must escalate, not complete"
    )


def test_all_four_required_params_really_are_required(doc):
    params = doc["params"]
    for name in (
        "candidates",
        "already_built_inventory",
        "rejected_components",
        "absorption_budget",
    ):
        assert params[name].get("required") is True, f"{name} is not required"
        assert "default" not in params[name], (
            f"{name} carries a default, which would make the fail-closed gate unreachable"
        )
    assert params["absorption_budget"]["minimum"] == 0, (
        "a budget of zero must be expressible"
    )


def test_it_may_judge_but_never_search(doc):
    """This is what keeps it from collapsing into BP-GEM-01."""
    policy = doc["tool_policy"]
    assert policy["default"] == "deny"
    assert policy["network"] == "none"
    assert policy["source_policy"]["offline_only"] is True
    for tool in DISCOVERY_TOOLS:
        assert tool in policy["deny"], f"{tool} is not explicitly denied"
        assert tool not in policy["allow"]
    assert K.D.denied_tool_requests(doc) == []


def test_the_deterministic_stages_have_no_model_and_only_the_residue_does(doc):
    for stage_id in (
        "dedup",
        "anchor-check",
        "bus-check",
        "budget-fit",
        "emit-verdicts",
    ):
        unit = K.stage(doc, stage_id)["work_unit"]
        assert (
            unit["assigned_model_vendor_role"]["model"] == "none-deterministic-script"
        ), stage_id
        assert unit["retry_policy"].startswith("none"), stage_id
    residue = K.stage(doc, "residue-adjudication")["work_unit"]
    assert residue["assigned_model_vendor_role"]["model"] == "opus"
    assert doc["roles"]["adjudicator"]["speaking_rights"] == "on-request"


def test_the_residue_stage_is_skipped_when_nothing_is_ambiguous(doc):
    for variant in K.example(doc)["fact_variants"]:
        plan = K.plan_from_example(doc, facts=variant["facts"])
        assert sorted(plan.skipped) == sorted(variant["expected_skipped"])


def test_the_anchor_rejects_architectures_not_unfamiliar_ideas(doc):
    unit = K.stage(doc, "anchor-check")["work_unit"]
    assert "Unfamiliarity is NOT a reason" in unit["question_or_target"]
    tests = " | ".join(unit["tests_required"])
    assert "vector-DB memory" in tests
    assert "novelty filter" in tests, (
        "the anchor must be tested for over-rejection too, or it ossifies the estate"
    )


def test_the_budget_is_a_hard_cap_and_zero_is_honoured(doc):
    unit = K.stage(doc, "budget-fit")["work_unit"]
    tests = " | ".join(unit["tests_required"])
    assert "budget 0" in tests
    assert "never exceed the budget" in tests
    gate = doc["gates"]["budget-respected"]
    assert "adopt_plus_build_verdicts <= absorption_budget" in gate["expression"]
    assert "verdicts_without_reason_code == 0" in gate["expression"]


def test_every_candidate_is_accounted_for_at_the_end(doc):
    unit = K.stage(doc, "emit-verdicts")["work_unit"]
    assert "row count must equal the input candidate count" in " | ".join(
        unit["tests_required"]
    )
    assert "reconciles its row count" in unit["evidence_requirement"]


def test_it_is_deterministic_and_replayable(doc):
    assert doc["replay"]["deterministic"] is True
    assert doc["replay"]["verify"] == "hash-equal"
    assert doc["retry_policy"]["strategy"] == "none"
    assert doc["failure_policy"]["on_failure"] == "fail-fast"


def test_it_is_composed_by_the_sweep_rather_than_duplicating_it(doc):
    ext = doc["x_extensions"]
    assert "bp-gem-01" in ext["why_not_a_duplicate_of_bp_gem_01"].lower()
    consumers = doc["outputs"]["verdicts"]["consumers"]
    assert "bp-gem-01-wide-lens-gem-sweep" in consumers


# ------------------------------------------------------------- mutation controls


def test_mutation_giving_the_inventory_param_a_default_defeats_the_fail_closed_design(
    doc,
):
    def inventory_has_no_default(d) -> bool:
        spec = d["params"]["already_built_inventory"]
        return spec.get("required") is True and "default" not in spec

    def mutate(d):
        spec = d["params"]["already_built_inventory"]
        spec.pop("required", None)
        spec["default"] = "command-center/EMPTY.json"

    K.both_states(doc, mutate, inventory_has_no_default, "inventory silently defaulted")


def test_mutation_a_required_param_with_a_default_is_schema_rejected(doc):
    """The schema itself forbids the contradiction, which is a second independent signal."""

    def mutate(d):
        d["params"]["already_built_inventory"]["default"] = "command-center/EMPTY.json"

    K.both_states(doc, mutate, K.is_conformant, "required param carrying a default")


def test_mutation_moving_the_completeness_gate_later_is_detectable(doc):
    def gate_is_first(d) -> bool:
        try:
            return K.plan_from_example(d).stage_order[0] == "input-completeness-gate"
        except K.D.PlanError:
            return False

    def mutate(d):
        for st in d["stages"]:
            if st.get("id") == "input-completeness-gate":
                st["depends_on"] = ["budget-fit"]
            if st.get("id") == "dedup":
                st["depends_on"] = []

    K.both_states(
        doc, mutate, gate_is_first, "completeness gate demoted to a post-hoc check"
    )


def test_mutation_allowing_a_discovery_tool_is_detectable(doc):
    def cannot_search(d) -> bool:
        policy = d["tool_policy"]
        return (
            all(t in policy["deny"] for t in DISCOVERY_TOOLS)
            and policy["network"] == "none"
        )

    def mutate(d):
        policy = d["tool_policy"]
        policy["deny"] = [t for t in policy["deny"] if t != "WebSearch"]
        policy["allow"].append("WebSearch")
        policy["network"] = "read-only"

    K.both_states(doc, mutate, cannot_search, "the judge acquired a search tool")


def test_mutation_routing_a_deterministic_stage_to_a_model_is_detectable(doc):
    def dedup_is_a_script(d) -> bool:
        return (
            K.stage(d, "dedup")["work_unit"]["assigned_model_vendor_role"]["model"]
            == "none-deterministic-script"
        )

    def mutate(d):
        for st in d["stages"]:
            if st.get("id") == "dedup":
                st["work_unit"]["assigned_model_vendor_role"]["model"] = "opus"

    K.both_states(
        doc, mutate, dedup_is_a_script, "set membership handed to model judgement"
    )


def test_mutation_dropping_the_budget_condition_from_the_gate_is_detectable(doc):
    def budget_enforced(d) -> bool:
        return (
            "adopt_plus_build_verdicts <= absorption_budget"
            in d["gates"]["budget-respected"]["expression"]
        )

    K.both_states(
        doc,
        lambda d: d["gates"]["budget-respected"].__setitem__(
            "expression", "verdicts_without_reason_code == 0"
        ),
        budget_enforced,
        "absorption budget stopped being a cap",
    )
