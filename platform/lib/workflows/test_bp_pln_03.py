"""End-to-end test for BP-PLN-03 (Multi-PR Stacking-Order Planner).

Executes the byte-identity classifier, the revision-containment test and the surface-ranked
ordering against the blueprint's worked example. The declared control changes only the BYTES of the
shared file and must flip the pair from stackable to conflicting - which proves the digest, not the
shared path, is doing the work.
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
    worked_example,
)

BP = "bp-pln-03.multi-pr-stacking-order-planner"


def blueprint():
    return load_blueprint(BP)


def _content(spec):
    return {path: text.encode("utf-8") for path, text in spec.items()}


def test_contract_layers():
    assert_contract_valid(blueprint())


def test_it_references_the_same_shared_overlap_primitive_as_pln_02():
    d = blueprint()
    ref = (d.get("subworkflows") or {})["shared.pairwise-overlap-matrix"]
    assert ref["workflow_id"] == "shared.pairwise-overlap-matrix"
    assert (REPO_ROOT / ref["source"]).is_file()
    assert stage(d, "s1-matrix")["kind"] == "subworkflow"


def test_worked_example_byte_identical_overlap_is_stackable():
    ex = worked_example(blueprint())
    a = _content(ex["input"]["pr1_content"])
    b = _content(ex["input"]["pr2_content"])
    identical, conflict = m.classify_overlap(a, b)
    assert sorted(identical) == ex["expected"]["pr1_pr2_identical"]
    assert sorted(conflict) == ex["expected"]["pr1_pr2_conflicts"] == []


def test_worked_example_differing_bytes_on_the_same_path_are_a_true_conflict():
    ex = worked_example(blueprint())
    a = _content(ex["input"]["pr1_content"])
    c = _content(ex["input"]["pr3_content"])
    _identical, conflict = m.classify_overlap(a, c)
    assert sorted(conflict) == ex["expected"]["pr1_pr3_conflicts"] == ["ci.yml"]


def test_worked_example_superset_relation_is_detected_directionally():
    ex = worked_example(blueprint())
    commits = ex["input"]["commits"]
    assert (
        m.is_superset(commits["pr1"], commits["pr2"])
        is ex["expected"]["pr2_supersets_pr1"]
    )
    assert m.is_superset(commits["pr2"], commits["pr1"]) is False


def test_worked_example_order_is_ranked_by_measured_surface():
    ex = worked_example(blueprint())
    order = m.merge_order(list(ex["input"]["surface"]), {}, ex["input"]["surface"])
    assert order == ex["expected"]["order"]


def test_declared_control_changing_only_the_bytes_flips_stackable_to_conflicting():
    ex = worked_example(blueprint())
    control = ex["controls"][0]
    a = _content(ex["input"]["pr1_content"])
    mutated_b = dict(ex["input"]["pr2_content"])
    mutated_b["ci.yml"] = "on: schedule\n"
    _identical, conflict = m.classify_overlap(a, _content(mutated_b))
    assert sorted(conflict) == control["expected_pr1_pr2_conflicts"] == ["ci.yml"]


def test_the_order_may_not_be_derived_from_mergestatestatus_alone():
    d = blueprint()
    assert gate_expressions(d)["no-mergestate-shortcut"] == (
        "order_derived_from_mergestatestatus_alone == false"
    )
    assert d["gates"]["no-mergestate-shortcut"]["on_fail"] == "fail"


def test_cost_is_counted_in_unmerged_paths_never_estimated_from_diff_size():
    d = blueprint()
    assert gate_expressions(d)["surface-measured-not-estimated"] == (
        "conflict_surface_from_line_count == false AND unmerged_paths_counted == true"
    )
    unit = stage(d, "s3-surface")["work_unit"]
    assert any("must report the SMALL number" in t for t in unit["tests_required"])


def test_every_merge_probe_runs_on_a_throwaway_branch_and_is_aborted():
    d = blueprint()
    assert d["params"]["probe_branch_prefix"]["default"].startswith("throwaway/")
    assert gate_expressions(d)["probe-tree-clean"] == (
        "probe_branches_abandoned == probe_branches_created AND working_tree_dirty == false"
    )
    unit = stage(d, "s3-surface")["work_unit"]
    assert any("must be aborted" in t for t in unit["tests_required"])
    assert "dirty-probe-tree" in unit["failure_classification"]


def test_changed_files_use_a_three_dot_diff_not_a_two_dot_one():
    unit = stage(blueprint(), "s0-changed-files")["work_unit"]
    assert "base...head" in unit["question_or_target"]
    assert any("two-dot diff must be rejected" in t for t in unit["tests_required"])
    assert any("mass deletion" in t for t in unit["tests_required"])


def test_digests_are_taken_from_the_committed_blob_not_the_working_tree():
    """Line endings differ between the two on this platform, so the source matters."""
    unit = stage(blueprint(), "s2-byte-identity")["work_unit"]
    assert any(
        "committed blob" in t and "line endings" in t for t in unit["tests_required"]
    )


def test_the_order_is_stable_and_a_superseded_pr_is_dropped_from_it():
    unit = stage(blueprint(), "s5-order")["work_unit"]
    assert any("stable across two runs" in t for t in unit["tests_required"])
    assert any(
        "must not appear in the order at all" in t for t in unit["tests_required"]
    )


def test_the_byte_identity_bound_is_disclosed():
    bound = blueprint()["x_extensions"]["honest_bound"]
    assert "incomplete conflict predictor" in bound
    assert "semantic judge" in bound


def test_a_single_unsuperseded_pr_completes_immediately():
    rule = declared_stopping_rule(blueprint(), "all-superseded")
    assert rule["expression"] == "unsuperseded_prs <= 1"
    assert rule["on_stop"] == "complete"


def test_two_prs_are_the_minimum_because_one_pr_has_no_ordering_problem():
    assert blueprint()["params"]["prs"]["min_items"] == 2


def test_the_forge_credential_is_declared_as_a_secret_ref_and_never_travels():
    """This is the only blueprint in the range that talks to a forge, so it is the only one that
    declares a credential - and declaring it is what makes the redaction rule checkable."""
    d = blueprint()
    spec = d["params"]["forge_token"]
    assert spec["type"] == "secret_ref"
    assert spec["secret"] is True
    assert "default" not in spec, "a secret_ref can never carry a literal default value"
    assert d["portability"]["export"]["redact_secrets"] is True
    assert "Bash:gh" in d["tool_policy"]["allow"], (
        "the credential exists because gh is allowed"
    )
    # the description must promise reference-only travel, not merely mention a secret
    assert "only this reference name travels" in spec["description"]
    assert "never reads, prints or rotates" in spec["description"]


# ------------------------------------------------------------------- both-states controls


def _invariant_probe_tree_must_be_clean(d):
    assert gate_expressions(d)["probe-tree-clean"] == (
        "probe_branches_abandoned == probe_branches_created AND working_tree_dirty == false"
    )
    assert d["gates"]["probe-tree-clean"]["on_fail"] == "fail"


def test_mutation_control_dropping_the_clean_tree_requirement_breaks_the_invariant():
    both_states_control(
        blueprint(),
        _invariant_probe_tree_must_be_clean,
        lambda x: x["gates"]["probe-tree-clean"].__setitem__(
            "expression", "probe_branches_created >= 0"
        ),
        "a merge probe could now leave the working tree dirty",
    )


def _invariant_byte_identity_decides_stackability(d):
    ex = worked_example(d)
    a = _content(ex["input"]["pr1_content"])
    b = _content(ex["input"]["pr2_content"])
    identical, conflict = m.classify_overlap(a, b)
    assert sorted(identical) == ex["expected"]["pr1_pr2_identical"]
    assert sorted(conflict) == ex["expected"]["pr1_pr2_conflicts"]


def test_mutation_control_changing_the_example_bytes_breaks_the_invariant():
    both_states_control(
        blueprint(),
        _invariant_byte_identity_decides_stackability,
        lambda x: x["x_extensions"]["worked_example"]["input"][
            "pr2_content"
        ].__setitem__("ci.yml", "on: schedule\n"),
        "the example's shared file is no longer byte-identical",
    )
