"""End-to-end test for BP-REQ-05 (Intent-to-PRD with Testability Lint).

The distinguishing property is ORDERING: two mechanical lints gate the adversarial trio, so no
reviewer budget is spent on a document a script can reject. Both lints are executed here against
the blueprint's declared worked example.
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
    worked_example,
)

BP = "bp-req-05.intent-to-prd-with-reviewer"


def blueprint():
    return load_blueprint(BP)


def test_contract_layers():
    assert_contract_valid(blueprint())


def test_both_lints_gate_the_reviewers_not_the_other_way_round():
    d = blueprint()
    assert stage(d, "s1-lint")["kind"] == "gate"
    assert stage(d, "s1b-trace")["kind"] == "gate"
    assert stage(d, "s1-lint")["depends_on"] == ["s0-author"]
    assert stage(d, "s1b-trace")["depends_on"] == ["s1-lint"]
    # the reviewer fan-out may only start after BOTH lints
    assert stage(d, "s2-review")["depends_on"] == ["s1b-trace"]
    assert stage(d, "s2-review")["kind"] == "fanout"


def test_the_testability_lint_fails_hard_unless_the_owner_opted_out():
    d = blueprint()
    assert gate_expressions(d)["testability-lint"] == (
        "untestable_requirements == 0 OR allow_unverifiable == true"
    )
    assert d["gates"]["testability-lint"]["on_fail"] == "fail"
    assert d["params"]["allow_unverifiable"]["default"] is False


def test_the_traceability_lint_has_no_opt_out():
    d = blueprint()
    assert gate_expressions(d)["traceability-lint"] == "orphan_requirements == 0"
    assert d["gates"]["traceability-lint"]["on_fail"] == "fail"


def test_worked_example_testability_verdicts_match_the_declared_expectations():
    ex = worked_example(blueprint())
    got = {rid: m.is_testable(text) for rid, text in ex["input"]["criteria"].items()}
    assert got == ex["expected"]["testable"]
    # and the two directions are both represented, so the lint is not a constant
    assert True in got.values() and False in got.values()


def test_worked_example_orphan_detection_matches_the_declared_expectations():
    ex = worked_example(blueprint())
    got = m.orphan_requirements(ex["input"]["ancestors"], ex["input"]["decision_ids"])
    assert got == ex["expected"]["orphans"]


def test_declared_control_rewriting_the_vague_criterion_makes_it_testable():
    control = worked_example(blueprint())["controls"][0]
    assert control["expected_testable"] is True
    assert m.is_testable("p95 export latency <= 2000 ms") is True


def test_all_three_lenses_must_pass_and_a_fourth_is_cross_vendor():
    d = blueprint()
    assert gate_expressions(d)["trio-pass"] == "reviewers_passed == 3"
    assert d["roles"]["scope_reviewer"]["cross_vendor_required"] is True
    assert d["roles"]["scope_reviewer"]["vendor"] == "openai"
    for lens in ("feasibility_reviewer", "completeness_reviewer", "scope_reviewer"):
        assert d["roles"][lens]["authority"] == "veto"
        assert d["roles"][lens]["independence"] == "independent"


def test_revision_loop_is_bounded_and_converges_on_both_lint_metrics():
    conv = stage(blueprint(), "s3-revise")["convergence"]
    assert conv["max_iterations"] == 3
    assert conv["no_progress_rounds"] == 2
    metrics = {mt["name"] for mt in conv["metrics"]}
    assert metrics == {"blocking_items", "untestable_requirements"}
    assert conv["on_no_convergence"] == "escalate"


def test_an_unverifiable_requirement_needs_explicit_owner_acceptance():
    st = stage(blueprint(), "s3b-owner-accept")
    assert st["kind"] == "human_checkpoint"
    assert st["when"] == "untestable_requirements > 0"
    assert st["owner_approval_required"] is True
    assert st["on_timeout"] == "fail", "an unanswered acceptance must not silently proceed"


def test_an_open_decision_log_escalates_rather_than_producing_fiction():
    rule = declared_stopping_rule(blueprint(), "decision-log-open")
    assert rule["expression"] == "decision_log_closed == false"
    assert rule["on_stop"] == "escalate"


# ------------------------------------------------------------------- both-states controls


def _invariant_lints_precede_reviewers(d):
    assert stage(d, "s2-review")["depends_on"] == ["s1b-trace"]
    assert d["gates"]["testability-lint"]["on_fail"] == "fail"


def test_mutation_control_letting_reviewers_run_before_the_lint_breaks_the_invariant():
    both_states_control(
        blueprint(),
        _invariant_lints_precede_reviewers,
        lambda x: stage(x, "s2-review").__setitem__("depends_on", ["s0-author"]),
        "reviewer fan-out bypasses the mechanical lints",
    )


def _invariant_orphans_block(d):
    assert gate_expressions(d)["traceability-lint"] == "orphan_requirements == 0"


def test_mutation_control_weakening_the_traceability_lint_breaks_the_invariant():
    both_states_control(
        blueprint(),
        _invariant_orphans_block,
        lambda x: x["gates"]["traceability-lint"].__setitem__("expression", "orphan_requirements >= 0"),
        "traceability lint made vacuously true",
    )
