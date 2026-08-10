"""End-to-end test for BP-PLN-02 (File-Disjoint Work-Unit Decomposition).

Fully executable: the blueprint's worked example is run through the real overlap matrix, the real
connected-component grouping and the real isolation assignment, and the declared control proves
that the single serial group came from the UNKNOWN handling rather than from the arithmetic.
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

BP = "bp-pln-02.file-disjoint-work-unit-decomposition"


def blueprint():
    return load_blueprint(BP)


def _example_sets(ex):
    return ex["input"]["path_sets"]


def test_contract_layers():
    assert_contract_valid(blueprint())


def test_it_references_the_shared_overlap_primitive_rather_than_carrying_a_copy():
    d = blueprint()
    assert "shared.pairwise-overlap-matrix" in (d.get("subworkflows") or {})
    st = stage(d, "s1-matrix")
    assert st["kind"] == "subworkflow"
    assert st["workflow"]["workflow_id"] == "shared.pairwise-overlap-matrix"
    src = d["subworkflows"]["shared.pairwise-overlap-matrix"]["source"]
    from bp3_testkit import REPO_ROOT

    assert (REPO_ROOT / src).is_file(), f"declared subworkflow source is not on disk: {src}"


def test_worked_example_overlap_pairs_match_the_declared_expectations():
    ex = worked_example(blueprint())
    ov = m.pairwise_overlap(_example_sets(ex))
    got = sorted([list(pair) for pair in ov])
    assert got == sorted(ex["expected"]["overlap_pairs"])


def test_worked_example_serial_groups_match_the_declared_expectations():
    ex = worked_example(blueprint())
    sets = _example_sets(ex)
    ov = m.pairwise_overlap(sets)
    assert m.serial_groups(list(sets), ov) == ex["expected"]["serial_groups"]


def test_worked_example_isolation_assignment_matches_and_unknown_is_serial():
    ex = worked_example(blueprint())
    iso = m.assign_isolation(_example_sets(ex), mutating=ex["input"]["mutating"])
    assert iso == ex["expected"]["isolation"]
    assert iso["u4"] == "serial"
    assert set(v for k, v in iso.items() if k != "u4") == {"worktree"}


def test_declared_control_knowing_u4s_footprint_splits_the_graph_into_three():
    """This is the control that isolates WHICH rule produced the single group."""
    ex = worked_example(blueprint())
    control = ex["controls"][0]
    sets = dict(_example_sets(ex))
    sets["u4"] = ["tests/test_c.py"]
    ov = m.pairwise_overlap(sets)
    assert m.serial_groups(list(sets), ov) == control["expected_serial_groups"]
    assert len(control["expected_serial_groups"]) == 3


def test_worktree_isolation_is_the_default_for_every_mutating_unit():
    d = blueprint()
    assert gate_expressions(d)["worktree-is-the-default"] == "mutating_units_without_worktree == 0"
    assert d["gates"]["worktree-is-the-default"]["on_fail"] == "fail"
    unit = stage(d, "s2-group")["work_unit"]
    assert any("the default is not scoped-add" in t for t in unit["tests_required"])


def test_a_scoped_add_unit_must_use_explicit_paths_and_verify_the_staged_diff():
    d = blueprint()
    assert gate_expressions(d)["no-broad-add"] == (
        "scoped_add_units_using_add_all == 0 AND staged_diff_verified == true"
    )
    assert d["gates"]["no-broad-add"]["on_fail"] == "fail"


def test_an_undeterminable_footprint_is_serialised_by_adverse_inference():
    d = blueprint()
    assert gate_expressions(d)["unknown-footprint-serialised"] == (
        "unknown_footprint_units_parallelised == 0"
    )
    unit = stage(d, "s0-enumerate")["work_unit"]
    assert any("never as an empty set" in t for t in unit["tests_required"])
    assert any("must be distinguishable" in t for t in unit["tests_required"])


def test_the_import_closure_widening_defaults_on_because_an_edit_can_force_a_caller_change():
    spec = blueprint()["params"]["widen_by_import_closure"]
    assert spec["default"] is True
    assert "caller" in spec["description"]


def test_it_claims_full_determinism_and_therefore_verifies_by_hash():
    d = blueprint()
    assert d["replay"]["deterministic"] is True
    assert d["replay"]["verify"] == "hash-equal"
    assert d["retry_policy"]["strategy"] == "none"


def test_the_measured_two_point_seven_percent_gap_is_stated():
    note = blueprint()["x_extensions"]["measured_gap_closed"]
    assert "9 of 329" in note and "2.7%" in note


def test_the_everything_overlaps_degenerate_case_emits_partial():
    rule = declared_stopping_rule(blueprint(), "everything-overlaps")
    assert rule["on_stop"] == "emit-partial"
    assert "serial_groups == 1" in rule["expression"]


# ------------------------------------------------------------------- both-states controls


def _invariant_unknown_is_serialised(d):
    assert gate_expressions(d)["unknown-footprint-serialised"] == (
        "unknown_footprint_units_parallelised == 0"
    )
    ex = worked_example(d)
    iso = m.assign_isolation(_example_sets(ex), mutating=ex["input"]["mutating"])
    assert iso["u4"] == "serial"


def test_mutation_control_weakening_the_unknown_gate_breaks_the_invariant():
    both_states_control(
        blueprint(),
        _invariant_unknown_is_serialised,
        lambda x: x["gates"]["unknown-footprint-serialised"].__setitem__(
            "expression", "unknown_footprint_units_parallelised >= 0"
        ),
        "an undeterminable footprint could now be parallelised optimistically",
    )


def _invariant_example_expectations_are_the_real_output(d):
    ex = worked_example(d)
    sets = _example_sets(ex)
    ov = m.pairwise_overlap(sets)
    assert m.serial_groups(list(sets), ov) == ex["expected"]["serial_groups"]


def test_mutation_control_editing_the_declared_expectation_breaks_the_invariant():
    """Proves the worked example is EXECUTED, not merely read."""
    both_states_control(
        blueprint(),
        _invariant_example_expectations_are_the_real_output,
        lambda x: x["x_extensions"]["worked_example"]["expected"].__setitem__(
            "serial_groups", [["u1"], ["u2"], ["u3"], ["u4"]]
        ),
        "declared expectation no longer matches the executed mechanism",
    )
