"""End-to-end test for BP-ARC-01 (Architecture Tournament with Minority-Report Fold-In).

Three properties are executed rather than asserted in prose: a critical error eliminates in round
one, a near-duplicate architecture is an independence failure, and the minority report is non-empty
whenever some loser out-scored the champion on some dimension.
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

BP = "bp-arc-01.architecture-tournament"


def blueprint():
    return load_blueprint(BP)


def _cands(spec):
    return [
        m.Architecture(
            name=a["name"],
            scores=a["scores"],
            critical_errors=a["critical_errors"],
            fingerprint=a["fingerprint"],
        )
        for a in spec
    ]


def test_contract_layers():
    assert_contract_valid(blueprint())


def test_the_rubric_is_frozen_before_generation():
    """Stage order is the anti-post-hoc-rationalisation mechanism."""
    d = blueprint()
    ids = stage_ids(d)
    assert ids.index("s0-freeze-rubric") < ids.index("s1-generate")
    assert stage(d, "s1-generate")["depends_on"] == ["s0-freeze-rubric"]
    assert (
        "rubric_changed_after_generation == false"
        in gate_expressions(d)["rubric-frozen"]
    )


def test_architects_generate_in_isolation():
    d = blueprint()
    assert d["roles"]["architect"]["independence"] == "independent"
    assert d["roles"]["architect"]["effort"] == "max"
    assert stage(d, "s1-generate")["kind"] == "fanout"
    assert d["roles"]["architect"]["min_participants"] == 2


def test_a_second_judge_is_cross_vendor_so_a_shared_blind_spot_cannot_decide():
    d = blueprint()
    assert d["roles"]["cross_vendor_judge"]["cross_vendor_required"] is True
    assert (
        d["roles"]["cross_vendor_judge"]["vendor"]
        != d["roles"]["bracket_judge"]["vendor"]
    )


def test_worked_example_eliminates_the_fatal_candidate_in_round_one():
    ex = worked_example(blueprint())
    cands = _cands(ex["input"]["architectures"])
    live, eliminated = m.eliminate_critical(cands)
    assert eliminated == ex["expected"]["eliminated"]
    assert "alpha" not in [c.name for c in live]


def test_worked_example_flags_the_near_duplicate_pair():
    ex = worked_example(blueprint())
    dups = m.near_duplicates(_cands(ex["input"]["architectures"]))
    assert [list(p) for p in dups] == ex["expected"]["near_duplicate_pairs"]


def test_worked_example_champion_and_minority_report_match_the_declared_expectations():
    ex = worked_example(blueprint())
    champ, rounds = m.bracket(
        _cands(ex["input"]["architectures"]), ex["input"]["weights"]
    )
    assert champ == ex["expected"]["champion"]
    for dim in ex["expected"]["minority_report_contains"]:
        assert dim in m.minority_report(rounds)
    # every round must name the dimension that decided it
    assert all(r["deciding_dimension"] in ex["input"]["weights"] for r in rounds)


def test_declared_control_without_the_override_the_fatal_design_would_have_won():
    """This is the control that proves the critical-error override is load-bearing."""
    ex = worked_example(blueprint())
    control = ex["controls"][0]
    cleared = [dict(a) for a in ex["input"]["architectures"]]
    for a in cleared:
        if a["name"] == "alpha":
            a["critical_errors"] = []
    champ, _ = m.bracket(_cands(cleared), ex["input"]["weights"])
    assert champ == control["expected_champion"] == "alpha"


def test_the_minority_report_and_its_fold_in_are_both_mandatory():
    d = blueprint()
    expr = gate_expressions(d)["minority-mandatory"]
    assert "minority_report_written == true" in expr
    assert "fold_in_decisions_recorded == true" in expr
    assert d["gates"]["minority-mandatory"]["on_fail"] == "fail"
    ids = stage_ids(d)
    assert ids.index("s3-minority") < ids.index("s4-fold-in") < ids.index("s4-gate")


def test_the_terminal_dossier_is_gated_by_the_shared_twelve_condition_predicate():
    d = blueprint()
    gate = d["gates"]["champion-artifact-complete"]
    assert gate["predicate"] == "completion-predicate-v1"
    assert gate["conditions_required"] == list(range(1, 13))
    assert stage(d, "s4b-predicate")["gate_ref"] == "champion-artifact-complete"


def test_an_unfixable_rubric_escalates_rather_than_degenerating_into_taste():
    rule = declared_stopping_rule(blueprint(), "criteria-not-fixable")
    assert rule["expression"] == "rubric_fixable == false"
    assert rule["on_stop"] == "escalate"


def test_bracket_loop_is_bounded():
    conv = stage(blueprint(), "s2-bracket")["convergence"]
    assert conv["max_iterations"] == 5
    assert conv["converged_when"] == "remaining_architectures == 1"


# ------------------------------------------------------------------- both-states controls


def _invariant_rubric_frozen_first(d):
    ids = stage_ids(d)
    assert ids.index("s0-freeze-rubric") < ids.index("s1-generate")
    assert (
        "rubric_changed_after_generation == false"
        in gate_expressions(d)["rubric-frozen"]
    )


def test_mutation_control_unfreezing_the_rubric_breaks_the_invariant():
    both_states_control(
        blueprint(),
        _invariant_rubric_frozen_first,
        lambda x: x["gates"]["rubric-frozen"].__setitem__(
            "expression", "rubric_hash_recorded == true"
        ),
        "rubric may now change after generation",
    )


def _invariant_minority_report_mandatory(d):
    assert d["gates"]["minority-mandatory"]["on_fail"] == "fail"
    assert (
        "fold_in_decisions_recorded == true"
        in gate_expressions(d)["minority-mandatory"]
    )


def test_mutation_control_making_the_minority_report_advisory_breaks_the_invariant():
    both_states_control(
        blueprint(),
        _invariant_minority_report_mandatory,
        lambda x: x["gates"]["minority-mandatory"].__setitem__(
            "on_fail", "record-and-continue"
        ),
        "minority report downgraded to advisory",
    )
