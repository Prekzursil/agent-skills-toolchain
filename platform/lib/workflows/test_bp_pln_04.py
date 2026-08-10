"""End-to-end test for BP-PLN-04 (Resume-Safe Program Checkpointing).

The load-bearing property is that completion is a POSTCONDITION on the artifact, evaluated by a
party that never reads the transcript. Two independent disqualifiers - the UNKNOWN marker and the
size floor - are executed separately, because a test that only ever trips both at once cannot tell
which one is working.
"""

from __future__ import annotations

import mechanisms as m
from bp3_testkit import (
    REPO_ROOT,
    assert_contract_valid,
    both_states_control,
    declared_stopping_rule,
    gate_expressions,
    load_blueprint,
    stage,
    stage_ids,
    worked_example,
)

BP = "bp-pln-04.resume-safe-program-checkpointing"


def blueprint():
    return load_blueprint(BP)


def test_contract_layers():
    assert_contract_valid(blueprint())


def test_it_references_the_shared_write_as_you_go_subworkflow():
    d = blueprint()
    ref = (d.get("subworkflows") or {})["shared.write-as-you-go-artifact"]
    assert (REPO_ROOT / ref["source"]).is_file()
    st = stage(d, "write-as-you-go")
    assert st["kind"] == "subworkflow"
    assert st["workflow"]["workflow_id"] == "shared.write-as-you-go-artifact"
    # the skeleton must be written BEFORE the unit runs
    assert stage(d, "run-unit")["depends_on"] == ["write-as-you-go"]


def test_worked_example_resume_plan_matches_the_declared_expectations():
    ex = worked_example(blueprint())
    plan = m.resume_plan(ex["input"]["artifacts"], min_bytes=ex["input"]["min_bytes"])
    assert plan == {"skip": ex["expected"]["skip"], "run": ex["expected"]["run"]}
    assert sorted(plan["skip"] + plan["run"]) == sorted(ex["input"]["artifacts"])


def test_worked_example_the_unknown_marker_alone_keeps_a_unit_out_of_skip():
    ex = worked_example(blueprint())
    u2 = ex["input"]["artifacts"]["u2"]
    assert m.UNKNOWN_MARKER in u2
    assert len(u2.encode("utf-8")) >= ex["input"]["min_bytes"], "u2 is above the floor on purpose"
    assert m.unit_complete(u2, ex["input"]["min_bytes"]) is False


def test_worked_example_the_size_floor_alone_keeps_a_unit_out_of_skip():
    ex = worked_example(blueprint())
    u3 = ex["input"]["artifacts"]["u3"]
    assert m.UNKNOWN_MARKER not in u3, "u3 is disqualified by size, not by the marker"
    assert m.unit_complete(u3, ex["input"]["min_bytes"]) is False


def test_declared_control_measuring_u2s_rows_moves_it_into_skip():
    ex = worked_example(blueprint())
    control = ex["controls"][0]
    measured = ex["input"]["artifacts"]["u2"].replace(m.UNKNOWN_MARKER, "3 groups, worktree")
    artifacts = dict(ex["input"]["artifacts"])
    artifacts["u2"] = measured
    plan = m.resume_plan(artifacts, min_bytes=ex["input"]["min_bytes"])
    assert plan["skip"] == control["expected_skip"]


def test_declared_control_lowering_the_floor_still_leaves_u2_in_run():
    """Proves the two disqualifiers are independent rather than one condition in disguise."""
    ex = worked_example(blueprint())
    control = ex["controls"][1]
    plan = m.resume_plan(ex["input"]["artifacts"], min_bytes=1)
    assert control["expected_run_contains"] in plan["run"]


def test_completion_is_never_self_report():
    d = blueprint()
    assert gate_expressions(d)["postcondition-not-self-report"] == (
        "units_marked_complete_without_artifact_check == 0"
    )
    keeper = d["roles"]["checkpoint_keeper"]
    assert "never asks a unit whether it finished" in keeper["description"]
    unit = stage(d, "s0-define-predicates")["work_unit"]
    assert any("that is self-report, not a postcondition" in t for t in unit["tests_required"])
    assert any("no size floor must be rejected" in t for t in unit["tests_required"])


def test_the_unknown_marker_disqualifies_completion_at_the_gate_too():
    d = blueprint()
    assert gate_expressions(d)["unknown-marker-is-not-complete"] == (
        "units_complete_with_unknown_markers == 0"
    )
    assert d["gates"]["unknown-marker-is-not-complete"]["on_fail"] == "fail"
    unit = stage(d, "s2-mark")["work_unit"]
    assert any("must be PARTIAL, never COMPLETE" in t for t in unit["tests_required"])
    assert any("known-incomplete artifact" in t for t in unit["tests_required"])


def test_no_resumable_boundary_may_be_wrapped_in_a_pipeline():
    d = blueprint()
    assert gate_expressions(d)["no-pipeline-around-a-resumable-boundary"] == (
        "resumable_boundaries_wrapped_in_pipeline == 0"
    )
    assert stage(d, "s4-pipeline-carveout")["kind"] == "gate"
    assert "pipeline-first-stage-rerun" in stage(d, "s3-resume")["work_unit"]["failure_classification"]


def test_the_pipeline_defect_is_marked_unverified_inline_with_a_settling_experiment():
    note = blueprint()["x_extensions"]["unverified_inline"]
    assert note.startswith("UNVERIFIED")
    assert "both-states probe" in note
    assert "Settling experiment" in note


def test_resume_is_keyed_per_work_unit_so_a_completed_sibling_is_not_re_run():
    d = blueprint()
    assert d["resume"]["enabled"] is True
    assert d["resume"]["granularity"] == "work-unit"
    assert "item_key" in d["resume"]["idempotency_key_from"]
    unit = stage(d, "s3-resume")["work_unit"]
    assert any("COMPLETE units must NOT re-run" in t for t in unit["tests_required"])
    assert any("exactly once" in t for t in unit["tests_required"])


def test_a_frozen_unit_is_distinguishable_from_a_slow_one():
    d = blueprint()
    assert d["params"]["heartbeat_seconds"]["default"] == 900
    assert "frozen" in stage(d, "run-unit")["work_unit"]["evidence_requirement"]


def test_the_barrier_has_a_deadline_and_a_partial_policy_so_stragglers_are_not_dropped():
    st = stage(blueprint(), "s1-run")
    assert st["barrier"]["mode"] == "deadline"
    assert st["barrier"]["deadline_seconds"] > 0
    assert st["barrier"]["on_partial"] == "proceed-with-quarantine"
    assert st["on_item_failure"] == "quarantine"


def test_dying_with_a_truthful_partial_emits_partial_rather_than_failing_silently():
    rule = declared_stopping_rule(blueprint(), "died-but-truthful")
    assert rule["on_stop"] == "emit-partial"
    assert "partial_artifacts_parse == true" in rule["expression"]


def test_partial_artifacts_live_under_the_artifact_root_not_in_temp():
    assert "never in temp" in blueprint()["params"]["artifact_root"]["description"]


def test_the_terminal_gate_is_the_shared_twelve_condition_predicate():
    d = blueprint()
    assert d["gates"]["unit-complete"]["conditions_required"] == list(range(1, 13))
    assert stage_ids(d)[-1] == "s5-predicate"


# ------------------------------------------------------------------- both-states controls


def _invariant_unknown_marker_blocks_completion(d):
    assert gate_expressions(d)["unknown-marker-is-not-complete"] == (
        "units_complete_with_unknown_markers == 0"
    )
    ex = worked_example(d)
    assert m.unit_complete(ex["input"]["artifacts"]["u2"], ex["input"]["min_bytes"]) is False


def test_mutation_control_removing_the_marker_from_the_example_breaks_the_invariant():
    both_states_control(
        blueprint(),
        _invariant_unknown_marker_blocks_completion,
        lambda x: x["x_extensions"]["worked_example"]["input"]["artifacts"].__setitem__(
            "u2", "pairs=12; groups=3; isolation=worktree; every row measured and cited."
        ),
        "the example no longer contains an unmeasured row, so the marker rule is untested",
    )


def _invariant_completion_is_a_postcondition(d):
    assert d["gates"]["postcondition-not-self-report"]["on_fail"] == "fail"
    assert d["roles"]["checkpoint_keeper"]["vendor"] == "any"


def test_mutation_control_downgrading_the_postcondition_gate_breaks_the_invariant():
    both_states_control(
        blueprint(),
        _invariant_completion_is_a_postcondition,
        lambda x: x["gates"]["postcondition-not-self-report"].__setitem__(
            "on_fail", "record-and-continue"
        ),
        "a unit could be marked complete without an artifact check",
    )
