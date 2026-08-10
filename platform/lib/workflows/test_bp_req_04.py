"""End-to-end test for BP-REQ-04 (Assumption-Ledger Elicitation).

The property that distinguishes this blueprint from BP-REQ-03 is its ACTUATOR: a low-confidence
load-bearing row goes to a cross-vendor verification PROBE, not to an owner question. That is
asserted structurally (the fan-out role is cross-vendor) and executably (the primitive reports the
unprobed row as unhandled).
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

BP = "bp-req-04.assumption-ledger-elicitation"


def blueprint():
    return load_blueprint(BP)


def test_contract_layers():
    assert_contract_valid(blueprint())


def test_stage_graph_covers_the_cards_s0_to_s4():
    ids = stage_ids(blueprint())
    for expected in ("s0-extract", "s0b-blanks", "s1-mark", "s2-rate", "s3-probe", "s3-gate", "s4-recheck"):
        assert expected in ids, f"{expected} missing from {ids}"


def test_s4_recheck_is_failure_triggered_not_scheduled():
    """The card is explicit: S4 fires on a step failure; it is not a scheduled stage."""
    st = stage(blueprint(), "s4-recheck")
    assert st["kind"] == "repair_loop"
    assert st["when"] == "step_failed == true"
    assert st["require_root_cause"] is True


def test_the_probe_is_cross_vendor_because_a_same_vendor_probe_inherits_the_blind_spot():
    d = blueprint()
    prober = d["roles"]["prober"]
    assert prober["cross_vendor_required"] is True
    assert prober["vendor"] == "openai"
    assert d["roles"]["rater"]["vendor"] == "anthropic"
    assert prober["vendor"] != d["roles"]["extractor"]["vendor"]


def test_the_probe_stage_is_a_fanout_bounded_by_the_probe_budget():
    d = blueprint()
    st = stage(d, "s3-probe")
    assert st["kind"] == "fanout"
    assert st["max_concurrency"] == d["params"]["probe_budget"]["default"]
    assert st["barrier"]["mode"] == "all" and st["barrier"]["on_partial"] == "fail"
    assert "started in the background" in st["barrier"]["reject_result_matching"]


def test_the_probe_unit_demands_a_source_probe_and_a_different_verifier():
    """An undeclared source measurement is zero signals, not one."""
    unit = stage(blueprint(), "probe-one")["work_unit"]
    assert "source measurement" in unit["evidence_requirement"]
    assert any("ORIGINAL probe must be rejected" in t for t in unit["tests_required"])
    assert "same-probe-rerun" in unit["failure_classification"]


def _rows(ex):
    return [
        m.Assumption(
            text=r["text"],
            load_bearing=r["load_bearing"],
            confidence=r["confidence"],
            verification_probe=r["verification_probe"],
        )
        for r in ex["input"]["rows"]
    ]


def test_worked_example_flags_only_the_unprobed_load_bearing_low_row():
    ex = worked_example(blueprint())
    unhandled = m.unhandled_assumptions(_rows(ex))
    assert [r.text for r in unhandled] == ex["expected"]["unhandled_texts"]


def test_worked_example_blank_required_field_resolves_to_the_worst_case():
    ex = worked_example(blueprint())
    blank = ex["input"]["blank_field"]
    assert m.blank_field_default(blank["declared"], blank["worst_case"]) == ex["expected"]["blank_resolves_to"]


def test_declared_control_probing_the_row_clears_the_gate():
    ex = worked_example(blueprint())
    rows = _rows(ex)
    rows[0] = m.Assumption(rows[0].text, True, "low", verification_probe="re-resolve the ref out of band")
    assert m.unhandled_assumptions(rows) == []


def test_gate_and_stopping_rule_both_forbid_carrying_a_silent_bet():
    d = blueprint()
    assert gate_expressions(d)["no-silent-bet"] == "low_confidence_load_bearing_unhandled == 0"
    rule = declared_stopping_rule(d, "ledger-clean")
    assert rule["expression"] == "low_confidence_load_bearing_unhandled == 0"
    assert rule["minimum_conditions"] == "rows_rated >= 1"


def test_an_unprobeable_assumption_emits_partial_with_its_blast_radius():
    rule = declared_stopping_rule(blueprint(), "probe-impossible")
    assert rule["on_stop"] == "emit-partial"
    assert "blast_radius" in rule["expression"]


# ------------------------------------------------------------------- both-states controls


def _invariant_prober_is_cross_vendor(d):
    assert d["roles"]["prober"]["cross_vendor_required"] is True
    assert d["roles"]["prober"]["vendor"] != d["roles"]["extractor"]["vendor"]


def test_mutation_control_making_the_prober_same_vendor_breaks_the_invariant():
    both_states_control(
        blueprint(),
        _invariant_prober_is_cross_vendor,
        lambda x: x["roles"]["prober"].update({"vendor": "anthropic", "cross_vendor_required": False}),
        "prober collapsed onto the extractor's vendor",
    )


def _invariant_recheck_is_failure_triggered(d):
    # .get, not [], so a missing key fails as a measured ASSERTION rather than crashing with a
    # KeyError - a control that reports a crash has not measured the property.
    assert stage(d, "s4-recheck").get("when") == "step_failed == true"


def test_mutation_control_scheduling_the_recheck_breaks_the_invariant():
    both_states_control(
        blueprint(),
        _invariant_recheck_is_failure_triggered,
        lambda x: stage(x, "s4-recheck").pop("when"),
        "recheck turned into a scheduled ritual stage",
    )
