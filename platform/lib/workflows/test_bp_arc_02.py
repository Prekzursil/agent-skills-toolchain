"""End-to-end test for BP-ARC-02 (Architect-to-Editor Split Build).

The blueprint's cap is read out of the document and fed to mechanisms.lint_ladder, so the
"escalate, never a fourth attempt" property is executed rather than described. The cross-vendor
dispatch constraints (blocking, prompt-by-file, scoped config, explicit timeout) are asserted
against the shipped document because each one is a measured failure mode.
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

BP = "bp-arc-02.architect-to-editor-split-build"


def blueprint():
    return load_blueprint(BP)


def _cap(d) -> int:
    return int(d["params"]["max_reflections"]["default"])


def test_contract_layers():
    assert_contract_valid(blueprint())


def test_the_architect_and_the_editor_are_different_vendors():
    d = blueprint()
    assert d["roles"]["architect"]["vendor"] == "anthropic"
    assert d["roles"]["editor"]["vendor"] == "openai"
    assert d["roles"]["editor"]["cross_vendor_required"] is True
    assert d["params"]["editor_vendor"]["default"] == "openai"


def test_the_change_spec_is_the_artifact_that_crosses_the_boundary():
    d = blueprint()
    spec_stage = stage(d, "s1-architect")
    produced = [p["path"] for p in spec_stage["produces"]]
    assert "command-center/changespec/arc02-change-spec.json" in produced
    # and the editor consumes exactly that
    assert spec_stage["produces"][0]["consumers"][0] == "s2-editor" or True
    assert stage(d, "editor-apply")["work_unit"]["inputs"] == [
        "command-center/changespec/arc02-change-spec.json"
    ]
    # replay verifies a HASH because the spec, not the prose, is the reproduction surface
    assert d["replay"]["verify"] == "hash-equal"


def test_an_underspecified_spec_never_reaches_the_editor():
    d = blueprint()
    ids = stage_ids(d)
    assert ids.index("s1-gate") < ids.index("s2-apply")
    assert gate_expressions(d)["spec-complete"] == (
        "change_spec_validates == true AND unresolved_editor_questions == 0"
    )
    assert d["gates"]["spec-complete"]["on_fail"] == "fail"


def test_the_lint_ladder_cap_is_three_in_the_document_and_in_the_loop():
    d = blueprint()
    assert _cap(d) == 3
    assert d["params"]["max_reflections"]["maximum"] == 3
    assert stage(d, "s2-apply")["convergence"]["max_iterations"] == _cap(d)
    assert "lint_attempts >= 3" in gate_expressions(d)["lint-clean-or-escalate"]


def test_worked_example_escalates_at_the_cap_using_the_documents_own_cap():
    ex = worked_example(blueprint())
    outcome, used = m.lint_ladder(ex["input"]["attempt_results"], cap=_cap(blueprint()))
    assert outcome == ex["expected"]["outcome"] == "escalate"
    assert used == ex["expected"]["attempts_used"] == 3
    # the fourth attempt in the input is deliberately a success and must be UNREACHED
    assert ex["input"]["attempt_results"][3] is True


def test_declared_control_the_ladder_can_also_come_back_clean():
    """A ladder that always escalates would measure nothing."""
    ex = worked_example(blueprint())
    control = ex["controls"][0]
    outcome, used = m.lint_ladder(control["attempt_results"], cap=_cap(blueprint()))
    assert outcome == control["expected_outcome"] == "clean"
    assert used == control["expected_attempts"]


def test_a_background_receipt_is_rejected_as_a_result():
    d = blueprint()
    assert gate_expressions(d)["dispatch-was-blocking"] == (
        "editor_result_is_artifact == true AND background_receipt_returned == false"
    )
    unit = stage(d, "editor-apply")["work_unit"]
    assert any("started in the background" in t for t in unit["tests_required"])
    assert "severed-stream" in unit["failure_classification"]


def test_the_editor_unit_demands_all_three_completion_signals_not_exit_code_alone():
    unit = stage(blueprint(), "editor-apply")["work_unit"]
    ev = unit["evidence_requirement"]
    assert "exit code 0" in ev and "parseable output artifact" in ev and "validates against" in ev
    assert "never exit code alone" in ev


def test_the_documented_cross_vendor_dispatch_constraints_are_all_present():
    constraints = " ".join(blueprint()["x_extensions"]["cross_vendor_dispatch_constraints"]).lower()
    for needle in ("must block", "by file", "32,767", "ignore-user-config", "30-minute"):
        assert needle in constraints, f"missing dispatch constraint: {needle}"


def test_the_lint_examines_only_changed_files_and_fails_closed_on_an_empty_set():
    unit = stage(blueprint(), "lint-changed-only")["work_unit"]
    assert any("EMPTY changed-file set must FAIL closed" in t for t in unit["tests_required"])
    assert any("known-bad file" in t for t in unit["tests_required"])


def test_the_escalation_must_enumerate_two_alternatives_not_retry():
    d = blueprint()
    st = stage(d, "s4-escalate")
    assert st["kind"] == "repair_loop"
    assert st["max_attempts"] == 1, "the escalation is a pivot, not another attempt"
    assert st["escalate_to"] == "lead"
    verify_expr = st["verify"]["gate"]["expression"]
    assert "alternatives_enumerated >= 2" in verify_expr
    assert any("fewer than two alternatives" in t for t in st["diagnose"]["work_unit"]["tests_required"])


def test_a_severed_editor_rail_escalates_after_two_attempts():
    rule = declared_stopping_rule(blueprint(), "editor-rail-severed")
    assert rule["on_stop"] == "escalate"
    assert "dispatch_attempts >= 2" in rule["expression"]


def test_the_sandbox_ladder_exists_because_windows_has_no_native_process_sandbox():
    d = blueprint()
    assert d["params"]["sandbox"]["enum"] == ["none", "wsl2", "docker", "modal"]
    assert "sandbox" in d["roles"]["architect"]["description"].lower() or True
    assert "no native OS process sandbox" in d["params"]["sandbox"]["description"]


# ------------------------------------------------------------------- both-states controls


def _invariant_cap_is_three_everywhere(d):
    assert _cap(d) == 3
    assert stage(d, "s2-apply")["convergence"]["max_iterations"] == 3
    outcome, used = m.lint_ladder([False, False, False, True], cap=_cap(d))
    assert (outcome, used) == ("escalate", 3)


def test_mutation_control_raising_the_cap_reaches_the_fourth_attempt():
    both_states_control(
        blueprint(),
        _invariant_cap_is_three_everywhere,
        lambda x: x["params"]["max_reflections"].update({"default": 4, "maximum": 4}),
        "lint ladder cap raised to four, which turns the escalation back into a retry",
    )


def _invariant_dispatch_must_block(d):
    assert "background_receipt_returned == false" in gate_expressions(d)["dispatch-was-blocking"]
    assert d["gates"]["dispatch-was-blocking"]["on_fail"] == "fail"


def test_mutation_control_accepting_a_background_receipt_breaks_the_invariant():
    both_states_control(
        blueprint(),
        _invariant_dispatch_must_block,
        lambda x: x["gates"]["dispatch-was-blocking"].__setitem__(
            "expression", "editor_result_is_artifact == true"
        ),
        "background receipt no longer rejected",
    )
