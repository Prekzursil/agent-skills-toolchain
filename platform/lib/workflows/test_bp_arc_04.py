"""End-to-end test for BP-ARC-04 (Failure-Domain Mapping Workshop).

Executes the whole ten-class catalogue walk. Three properties are load-bearing and all three are
executed: an applicable class with no probe is UNMONITORED, a try/except ImportError trait must
flag fail-open, and zero applicable domains must be REACHABLE so the walk is not rubber-stamping.
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

BP = "bp-arc-04.failure-domain-mapping-workshop"


def blueprint():
    return load_blueprint(BP)


def test_contract_layers():
    assert_contract_valid(blueprint())


def test_worked_example_walks_all_ten_classes():
    ex = worked_example(blueprint())
    rows = m.failure_domain_walk(ex["input"]["option_traits"], probes=ex["input"]["probes"])
    assert len(rows) == ex["expected"]["classes_walked"] == 10
    assert len(m.FAILURE_CLASSES) == 10


def test_worked_example_flags_fail_open_for_a_try_except_importerror_guard():
    ex = worked_example(blueprint())
    rows = m.failure_domain_walk(ex["input"]["option_traits"], probes=ex["input"]["probes"])
    applicable = [r.failure_class for r in rows if r.applies]
    assert applicable == ex["expected"]["applicable"]
    assert "fail-open-on-missing-dependency" in applicable


def test_worked_example_an_applicable_class_with_no_probe_is_unmonitored():
    ex = worked_example(blueprint())
    rows = m.failure_domain_walk(ex["input"]["option_traits"], probes=ex["input"]["probes"])
    assert m.unmonitored_domains(rows) == ex["expected"]["unmonitored"]
    # and 'who notices' is literally nobody for that domain, which is the disclosure the card wants
    unmon = [r for r in rows if r.unmonitored]
    assert unmon and all(r.who_notices == "nobody" for r in unmon)


def test_declared_control_supplying_the_probe_clears_the_unmonitored_flag():
    ex = worked_example(blueprint())
    probes = dict(ex["input"]["probes"])
    probes["fail-open-on-missing-dependency"] = "remove the import and assert the guard fires"
    rows = m.failure_domain_walk(ex["input"]["option_traits"], probes=probes)
    assert m.unmonitored_domains(rows) == []


def test_declared_control_zero_applicable_domains_is_reachable():
    """If every option always mapped to some domain, the walk would be rubber-stamping."""
    rows = m.failure_domain_walk([])
    assert [r.failure_class for r in rows if r.applies] == []
    assert len(rows) == 10


def test_zero_domains_is_treated_as_a_red_flag_not_a_green_light():
    d = blueprint()
    assert gate_expressions(d)["zero-domains-is-a-red-flag"] == (
        "domains_applicable >= 1 OR option_declared_under_specified == true"
    )
    assert d["gates"]["zero-domains-is-a-red-flag"]["on_fail"] == "fail"
    unit = stage(d, "map-one-option")["work_unit"]
    assert any("never accepted as safe" in t for t in unit["tests_required"])


def test_the_whole_catalogue_must_be_walked_not_a_subset():
    d = blueprint()
    assert gate_expressions(d)["catalogue-fully-walked"] == "classes_walked == classes_in_catalogue"
    assert d["gates"]["catalogue-fully-walked"]["on_fail"] == "fail"


def test_who_notices_may_not_be_the_agent_for_a_fail_open_class():
    unit = stage(blueprint(), "map-one-option")["work_unit"]
    assert any("the agent is exactly what does not notice" in t for t in unit["tests_required"])


def test_a_probe_claimed_to_exist_must_be_shown_to_fire_before_the_claim_is_accepted():
    unit = stage(blueprint(), "s3b-probe-inventory")["work_unit"]
    assert any("known-broken state" in t for t in unit["tests_required"])
    assert any("must-be-built, never assumed present" in t for t in unit["tests_required"])


def test_options_are_compared_on_domains_not_on_features():
    d = blueprint()
    unit = stage(d, "s4-compare")["work_unit"]
    assert "refusing to rank on feature count" in unit["question_or_target"]
    assert any("most features but the most unmonitored domains must not rank first" in t for t in unit["tests_required"])
    ids = stage_ids(d)
    assert ids.index("s3b-probe-inventory") < ids.index("s4-compare")


def test_a_failed_mapper_aborts_the_comparison_rather_than_producing_a_partial_table():
    st = stage(blueprint(), "s0-walk")
    assert st["on_item_failure"] == "abort"
    assert st["barrier"]["on_partial"] == "fail"


def test_an_option_whose_failure_modes_cannot_be_enumerated_escalates():
    rule = declared_stopping_rule(blueprint(), "option-not-enumerable")
    assert rule["expression"] == "failure_modes_enumerable == false"
    assert rule["on_stop"] == "escalate"


def test_the_catalogue_completeness_bound_is_disclosed_not_hidden():
    bound = blueprint()["x_extensions"]["honest_bound"]
    assert "catalogue completeness bounds" in bound
    assert "It maps; it does not prove" in bound


# ------------------------------------------------------------------- both-states controls


def _invariant_unmonitored_must_be_disclosed(d):
    assert gate_expressions(d)["unmonitored-declared"] == "unmonitored_domains_undisclosed == 0"
    assert d["gates"]["unmonitored-declared"]["on_fail"] == "fail"


def test_mutation_control_letting_an_unmonitored_domain_pass_silently_breaks_the_invariant():
    both_states_control(
        blueprint(),
        _invariant_unmonitored_must_be_disclosed,
        lambda x: x["gates"]["unmonitored-declared"].__setitem__("on_fail", "record-and-continue"),
        "an unmonitored failure domain would no longer block",
    )


def _invariant_probe_required_per_domain(d):
    assert d["params"]["require_probe_per_domain"]["default"] is True
    rows = m.failure_domain_walk(["try-except-importerror"], probes={})
    assert m.unmonitored_domains(rows) == ["fail-open-on-missing-dependency"]


def test_mutation_control_defaulting_probe_requirement_off_breaks_the_invariant():
    both_states_control(
        blueprint(),
        _invariant_probe_required_per_domain,
        lambda x: x["params"]["require_probe_per_domain"].__setitem__("default", False),
        "a domain could be called handled with no detection probe",
    )
