"""End-to-end test for BP-ARC-03 (Anti-Overfit Architecture Audit).

The load-bearing property is that DISARMED is never reported as UNUSED, and that absent telemetry
yields UNKNOWN rather than a presumption of deadness. Both are executed through
mechanisms.classify_component against the blueprint's own worked example, and the removal rule is
executed through mechanisms.removable.
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

BP = "bp-arc-03.anti-overfit-architecture-audit"


def blueprint():
    return load_blueprint(BP)


def test_contract_layers():
    assert_contract_valid(blueprint())


def test_worked_example_classifications_match_and_disarmed_is_distinct_from_unused():
    ex = worked_example(blueprint())
    got = {
        name: m.classify_component(
            registered=c["registered"],
            fired_recently=c["fired_recently"],
            fires_on_known_bad_state=c["fires_on_known_bad_state"],
        )
        for name, c in ex["input"]["components"].items()
    }
    assert got == ex["expected"]["classes"]
    # the two components with IDENTICAL telemetry must land in DIFFERENT classes: that is the
    # whole discrimination, and telemetry alone cannot make it
    assert got["stale-guard"] == "disarmed"
    assert got["quiet-guard"] == "live-dormant"
    stale = ex["input"]["components"]["stale-guard"]
    quiet = ex["input"]["components"]["quiet-guard"]
    assert stale["fired_recently"] == quiet["fired_recently"] is False


def test_worked_example_removability_matches_and_only_the_unregistered_one_is_eligible():
    ex = worked_example(blueprint())
    ctx = ex["input"]["removal_context"]
    got = sorted(
        name
        for name, c in ex["input"]["components"].items()
        if m.removable(
            m.classify_component(
                registered=c["registered"],
                fired_recently=c["fired_recently"],
                fires_on_known_bad_state=c["fires_on_known_bad_state"],
            ),
            blast_radius_traced=ctx["blast_radius_traced"],
            security_bearing=ctx["security_bearing"],
        )
    )
    assert got == ex["expected"]["removable"] == ["orphan-handler"]


def test_declared_controls_security_bearing_and_untraced_removals_are_both_refused():
    controls = worked_example(blueprint())["controls"]
    assert len(controls) == 2
    assert m.removable("unregistered", blast_radius_traced=True, security_bearing=True) is False
    assert m.removable("unregistered", blast_radius_traced=False, security_bearing=False) is False


def test_the_both_states_probe_gates_every_classification():
    d = blueprint()
    assert gate_expressions(d)["disarmed-distinguished"] == (
        "components_classified_without_both_states_probe == 0"
    )
    assert d["gates"]["disarmed-distinguished"]["on_fail"] == "fail"
    ids = stage_ids(d)
    assert ids.index("s1-gate") < ids.index("s2-judge")


def test_last_exercised_comes_from_telemetry_never_from_a_file_mtime():
    unit = stage(blueprint(), "audit-component")["work_unit"]
    assert "NEVER from a file mtime" in unit["evidence_requirement"]
    assert any("DISARMED, never as unused" in t for t in unit["tests_required"])
    assert any("UNKNOWN, never as dead" in t for t in unit["tests_required"])


def test_absent_telemetry_emits_partial_rather_than_declaring_components_dead():
    rule = declared_stopping_rule(blueprint(), "telemetry-absent")
    assert rule["expression"] == "telemetry_available == false"
    assert rule["on_stop"] == "emit-partial"
    assert rule["minimum_conditions"] == "components_inventoried >= 1"


def test_no_removal_proposal_without_a_traced_blast_radius():
    d = blueprint()
    assert gate_expressions(d)["no-untraced-removal"] == "removal_proposals_without_blast_radius == 0"
    assert d["gates"]["no-untraced-removal"]["on_fail"] == "fail"


def test_a_security_bearing_removal_is_owner_only_and_defaults_to_forbidden():
    d = blueprint()
    assert d["params"]["allow_security_removal"]["default"] is False
    st = stage(d, "s4-owner")
    assert st["kind"] == "human_checkpoint"
    assert st["approval_mode"] == "owner-only"
    assert st["on_timeout"] == "fail"
    assert "rule-category-out-of-scope" in st["options"]
    assert d["gates"]["security-removal-owner-only"]["on_fail"] == "escalate-to-human"


def test_the_removal_critic_argues_the_opposite_case_and_is_cross_vendor():
    d = blueprint()
    critic = d["roles"]["removal_critic"]
    assert critic["cross_vendor_required"] is True
    assert critic["authority"] == "veto"
    assert critic["independence"] == "cross-examining"
    assert critic["vendor"] != d["roles"]["component_auditor"]["vendor"]
    unit = stage(d, "s4-critic")["work_unit"]
    assert any("dormant security guard must survive" in t for t in unit["tests_required"])


def test_the_inventory_declares_its_search_scope_so_a_floor_is_not_read_as_a_total():
    unit = stage(blueprint(), "s0-inventory")["work_unit"]
    assert "search scope" in unit["evidence_requirement"]
    assert "detector-truncation" in unit["failure_classification"]


def test_the_audit_cannot_write_into_the_live_harness_trees_it_audits():
    forbidden = blueprint()["tool_policy"]["forbid_write_paths"]
    assert ".claude/hooks/**" in forbidden and ".claude/rules/**" in forbidden


def test_it_declares_why_it_is_not_a_duplicate_of_the_silent_disarm_hunt():
    note = blueprint()["x_extensions"]["not_a_duplicate_of_bp_dbg_05"]
    assert "BP-DBG-05" in note and "CONSUMES" in note


# ------------------------------------------------------------------- both-states controls


def _invariant_both_states_probe_required(d):
    assert (
        gate_expressions(d)["disarmed-distinguished"]
        == "components_classified_without_both_states_probe == 0"
    )
    assert d["gates"]["disarmed-distinguished"]["on_fail"] == "fail"


def test_mutation_control_dropping_the_both_states_requirement_breaks_the_invariant():
    both_states_control(
        blueprint(),
        _invariant_both_states_probe_required,
        lambda x: x["gates"]["disarmed-distinguished"].__setitem__("on_fail", "record-and-continue"),
        "classification without a both-states probe merely recorded",
    )


def _invariant_security_removal_is_owner_only(d):
    assert d["params"]["allow_security_removal"]["default"] is False
    assert stage(d, "s4-owner").get("approval_mode") == "owner-only"
    assert stage(d, "s4-owner").get("on_timeout") == "fail"


def test_mutation_control_letting_an_unanswered_security_removal_proceed_breaks_the_invariant():
    both_states_control(
        blueprint(),
        _invariant_security_removal_is_owner_only,
        lambda x: stage(x, "s4-owner").__setitem__("on_timeout", "proceed"),
        "an unanswered security-bearing removal would proceed",
    )
