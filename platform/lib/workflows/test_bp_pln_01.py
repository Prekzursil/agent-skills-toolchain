"""End-to-end test for BP-PLN-01 (Mechanical Plan-Lint then Adversarial Trio).

The defining property is that the two benchmark cases must be caught by DIFFERENT stages: the
missing-rollback plan by the deterministic lint, the structurally-perfect-but-infeasible plan by a
reviewer. A blueprint where one stage catches both has lost the property, so that separation is
asserted explicitly and the lint half is executed.
"""

from __future__ import annotations

import mechanisms as m
from bp3_testkit import (
    assert_contract_valid,
    both_states_control,
    declared_stopping_rule,
    gate_expressions,
    load_blueprint,
    stage,
    stage_ids,
    worked_example,
)

BP = "bp-pln-01.mechanical-plan-lint-then-adversarial-trio"


def blueprint():
    return load_blueprint(BP)


def test_contract_layers():
    assert_contract_valid(blueprint())


def test_the_hard_lint_gate_sits_between_the_lint_and_the_reviewers():
    d = blueprint()
    ids = stage_ids(d)
    assert ids.index("s0-lint") < ids.index("s0-gate") < ids.index("s1-review")
    assert stage(d, "s1-review")["depends_on"] == ["s0-gate"]
    assert gate_expressions(d)["lint-hard-pass"] == "lint_hard_violations == 0"
    assert d["gates"]["lint-hard-pass"]["on_fail"] == "fail"


def test_the_linter_is_a_script_with_no_model_route():
    """model_target has no honest 'not a model' vendor, so the linter is a ROLE with vendor=any."""
    d = blueprint()
    assert d["roles"]["linter"]["vendor"] == "any"
    assert d["roles"]["linter"]["authority"] == "veto"
    routed_conditions = [r["when"] for r in d["model_routing"].get("routes", [])]
    assert not any("linter" in c for c in routed_conditions)


def test_worked_example_lint_catches_plan_a_and_spends_no_reviewer():
    ex = worked_example(blueprint())
    plan_a = ex["input"]["plan_a"]
    # the lint's two mechanical rules, executed
    assert plan_a["has_rollback"] is False
    assert m.is_testable(plan_a["acceptance"]) is False
    assert ex["expected"]["plan_a_caught_by"] == "lint"
    assert ex["expected"]["plan_a_reviewers_spent"] == 0


def test_worked_example_plan_b_passes_the_lint_so_a_reviewer_must_catch_it():
    ex = worked_example(blueprint())
    plan_b = ex["input"]["plan_b"]
    assert plan_b["has_rollback"] is True
    assert "rollback" in plan_b["sections"]
    assert m.is_testable(plan_b["acceptance"]) is True
    assert ex["expected"]["plan_b_lint_violations"] == 0
    assert ex["expected"]["plan_b_caught_by"] == "reviewer"


def test_the_two_benchmark_cases_are_caught_by_different_stages():
    ex = worked_example(blueprint())
    assert ex["expected"]["plan_a_caught_by"] != ex["expected"]["plan_b_caught_by"]


def test_declared_control_the_lint_can_pass_so_it_is_not_permanently_red():
    control = worked_example(blueprint())["controls"][0]
    assert control["expected_lint_violations"] == 0
    assert m.is_testable("p95 latency <= 2000 ms over 100 runs") is True


def test_three_independent_lenses_run_in_parallel_each_with_veto():
    d = blueprint()
    st = stage(d, "s1-review")
    assert st["kind"] == "fanout"
    assert st["over"]["items"] == ["feasibility", "completeness", "scope"]
    assert st["max_concurrency"] == 3
    for lens in ("feasibility_lens", "completeness_lens", "scope_lens"):
        assert d["roles"][lens]["authority"] == "veto"
        assert d["roles"][lens]["independence"] == "independent"


def test_a_null_lens_cannot_be_counted_as_a_pass():
    d = blueprint()
    assert gate_expressions(d)["trio-unanimous"] == "lenses_passed == lenses_run AND lenses_run >= 3"
    unit = stage(d, "s2-aggregate")["work_unit"]
    assert any("two PASS plus one null lens must NOT aggregate" in t for t in unit["tests_required"])
    assert "lenses_run and lenses_passed are both recorded" in unit["completion_sentinel"]


def test_a_lint_over_an_empty_input_set_fails_closed():
    unit = stage(blueprint(), "s0-lint")["work_unit"]
    assert any("found zero inputs must FAIL closed" in t for t in unit["tests_required"])
    assert any("known-bad plan" in t for t in unit["tests_required"])
    assert "non-empty input set" in unit["completion_sentinel"]


def test_findings_a_script_could_have_made_are_reported_advisorily_not_blocking():
    d = blueprint()
    gate = d["gates"]["nothing-mechanical-sent-to-an-llm"]
    assert gate["blocking"] is False
    assert gate["on_fail"] == "record-and-continue"


def test_an_author_out_of_revisions_escalates():
    rule = declared_stopping_rule(blueprint(), "author-out-of-revisions")
    assert rule["on_stop"] == "escalate"
    assert rule["expression"] == "revisions_used >= 2"


def test_the_optional_fourth_lens_is_cross_vendor_and_off_by_default():
    d = blueprint()
    assert d["params"]["cross_vendor_fourth_lens"]["default"] is False
    assert d["roles"]["cross_vendor_lens"]["cross_vendor_required"] is True
    assert d["roles"]["cross_vendor_lens"]["vendor"] == "openai"


# ------------------------------------------------------------------- both-states controls


def _invariant_lint_gates_the_reviewers(d):
    assert stage(d, "s1-review")["depends_on"] == ["s0-gate"]
    assert d["gates"]["lint-hard-pass"]["on_fail"] == "fail"


def test_mutation_control_letting_reviewers_run_on_a_malformed_plan_breaks_the_invariant():
    both_states_control(
        blueprint(),
        _invariant_lint_gates_the_reviewers,
        lambda x: stage(x, "s1-review").__setitem__("depends_on", ["s0-lint"]),
        "reviewers would now run even when the lint fails hard",
    )


def _invariant_null_lens_is_not_a_pass(d):
    assert gate_expressions(d)["trio-unanimous"] == "lenses_passed == lenses_run AND lenses_run >= 3"


def test_mutation_control_dropping_the_lenses_run_floor_breaks_the_invariant():
    both_states_control(
        blueprint(),
        _invariant_null_lens_is_not_a_pass,
        lambda x: x["gates"]["trio-unanimous"].__setitem__("expression", "lenses_passed >= 2"),
        "two lenses plus a null lens would now pass the gate",
    )
