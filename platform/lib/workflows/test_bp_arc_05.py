"""End-to-end test for BP-ARC-05 (Vendor-Neutral Workflow Spec Emission).

The round-trip gate is executed against the blueprint's own worked example: identical topology
passes and a FLATTENED nested stage fails, which is the silent loss the gate exists to catch. The
two live spec-layer conflicts are asserted to be REQUIRED params with no default, so the blueprint
cannot silently pick a winner.
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

BP = "bp-arc-05.vendor-neutral-workflow-spec-emission"


def blueprint():
    return load_blueprint(BP)


def test_contract_layers():
    assert_contract_valid(blueprint())


def test_it_is_declared_a_meta_workflow():
    assert blueprint()["kind"] == "meta-workflow"


def test_the_two_live_conflicts_are_required_params_with_no_default():
    """A default here would silently resolve an owner decision. Both must be undefaulted."""
    d = blueprint()
    for name in ("max_threads", "worker_model_floor"):
        spec = d["params"][name]
        assert spec.get("required") is True, f"{name} is not required"
        assert "default" not in spec, f"{name} silently defaults, which picks a winner"
    assert d["params"]["worker_model_floor"]["enum"] == ["sonnet", "opus"]
    assert gate_expressions(d)["conflicts-resolved"] == (
        "max_threads_declared == true AND worker_model_floor_declared == true"
    )


def test_max_depth_is_pinned_at_one_level_of_nesting():
    spec = blueprint()["params"]["max_depth"]
    assert spec["minimum"] == spec["maximum"] == spec["default"] == 1
    assert "max_depth == 1" in gate_expressions(blueprint())["handoff-fields-exact"]


def test_worked_example_identical_topology_round_trips():
    ex = worked_example(blueprint())
    src = {"stages": ex["input"]["source_stages"]}
    assert m.roundtrip_equal(src, {"stages": ex["input"]["source_stages"]}) is ex["expected"]["identical_roundtrip"]
    assert len(m.topology(src)) == ex["expected"]["topology_length"] == 4


def test_worked_example_a_flattened_nested_stage_fails_the_round_trip():
    ex = worked_example(blueprint())
    control = ex["controls"][0]
    flattened = []
    for st in ex["input"]["source_stages"]:
        copy_st = dict(st)
        if "body" in copy_st:
            copy_st["body"] = []
        flattened.append(copy_st)
    assert m.roundtrip_equal({"stages": ex["input"]["source_stages"]}, {"stages": flattened}) is (
        control["expected_roundtrip"]
    )
    assert control["expected_roundtrip"] is False


def test_worked_example_a_stage_with_no_provider_cell_is_declared_vendor_locked():
    ex = worked_example(blueprint())
    locked = m.vendor_locked(
        [s["id"] for s in ex["input"]["source_stages"]], ex["input"]["provider_map"]
    )
    assert locked == ex["expected"]["vendor_locked"] == ["c"]


def test_a_round_trip_mismatch_rejects_the_spec_rather_than_patching_it():
    d = blueprint()
    assert gate_expressions(d)["roundtrip-equal"] == "roundtrip_topology_equal == true"
    assert d["gates"]["roundtrip-equal"]["on_fail"] == "fail"
    unit = stage(d, "s4-roundtrip")["work_unit"]
    assert "rejects the spec rather than retrying" in unit["retry_policy"]
    assert any("Dropping one stage" in t or "dropping one stage" in t.lower() for t in unit["tests_required"])


def test_no_stage_is_silently_dropped_for_a_vendor():
    d = blueprint()
    assert gate_expressions(d)["unsupported-declared"] == "silently_dropped_stages == 0"
    unit = stage(d, "s1-map")["work_unit"]
    assert "UNSUPPORTED" in unit["question_or_target"]
    assert any("never an absent cell" in t for t in unit["tests_required"])


def test_the_portability_critic_is_cross_vendor_because_lock_in_is_invisible_from_inside():
    d = blueprint()
    critic = d["roles"]["portability_critic"]
    assert critic["cross_vendor_required"] is True
    assert critic["authority"] == "veto"
    assert critic["vendor"] != d["roles"]["translator"]["vendor"]


def test_the_owner_checkpoint_comes_after_the_round_trip_gate():
    ids = stage_ids(blueprint())
    assert ids.index("s4-gate") < ids.index("s5-owner-conflicts") < ids.index("s5-gate")
    st = stage(blueprint(), "s5-owner-conflicts")
    assert st["approval_mode"] == "owner-only" and st["on_timeout"] == "fail"


def test_it_cannot_overwrite_the_workflow_tree_it_translates():
    assert "platform/workflows/**" in blueprint()["tool_policy"]["forbid_write_paths"]


def test_a_vendor_locked_feature_emits_partial_rather_than_faking_portability():
    rule = declared_stopping_rule(blueprint(), "no-cross-vendor-equivalent")
    assert rule["on_stop"] == "emit-partial"
    assert "declared_vendor_locked == true" in rule["expression"]


def test_the_anti_overfit_anchor_denies_a_second_orchestration_runtime():
    anchor = blueprint()["x_extensions"]["anti_overfit_anchor"]
    assert "NOT a second orchestration runtime" in anchor


# ------------------------------------------------------------------- both-states controls


def _invariant_conflicts_are_undefaulted(d):
    for name in ("max_threads", "worker_model_floor"):
        assert d["params"][name].get("required") is True
        assert "default" not in d["params"][name]


def test_mutation_control_defaulting_max_threads_breaks_the_invariant():
    both_states_control(
        blueprint(),
        _invariant_conflicts_are_undefaulted,
        lambda x: x["params"]["max_threads"].__setitem__("default", 4),
        "max_threads silently defaults to the lifecycle value, resolving an owner decision",
    )


def _invariant_roundtrip_rejects(d):
    assert d["gates"]["roundtrip-equal"]["on_fail"] == "fail"
    assert gate_expressions(d)["roundtrip-equal"] == "roundtrip_topology_equal == true"


def test_mutation_control_downgrading_the_roundtrip_gate_breaks_the_invariant():
    both_states_control(
        blueprint(),
        _invariant_roundtrip_rejects,
        lambda x: x["gates"]["roundtrip-equal"].__setitem__("on_fail", "record-and-continue"),
        "a topology mismatch would be recorded and shipped instead of rejected",
    )
