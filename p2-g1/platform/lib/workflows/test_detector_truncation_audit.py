"""FLAGSHIP end-to-end test for `detector-truncation-audit` (bp-8, slot 94, BP-MNT-03).

Mechanism claims under test: the second count must come from a MECHANICALLY DIFFERENT instrument -
re-running the same query with a bigger limit is the same signal twice; the independent counter must
not be able to read the reported figure first, which is enforced STRUCTURALLY by the fan-out body
graph (``count-independently`` does not depend on ``read-reported``, and only the comparison depends
on both); both instruments must be counting the same DEFINED population, or the difference measures
scope rather than truncation; and the pass condition is DISCLOSURE, not the absence of caps -
"showing 10 of 200" PASSES while an undisclosed cap is a correctness defect.

Every check ships with a targeted mutant and is asserted to FAIL on it.
"""

from __future__ import annotations

from typing import Any, Mapping

import bp8_testkit as K
import pytest

WORKFLOW_ID = "detector-truncation-audit"
DOC = K.load(WORKFLOW_ID)


# ------------------------------------------------------------------------------- the checks


def check_the_second_instrument_must_be_mechanically_different(
    doc: Mapping[str, Any],
) -> None:
    spec = K.gate_for_stage(doc, "gate-independence")
    assert "instruments_share_mechanism == false" in spec["expression"], (
        "re-running the same query with a bigger limit is one signal, not two"
    )
    assert "require_different_mechanism == true" in spec["expression"]
    assert spec["blocking"] is True and spec["on_fail"] == "fail"
    assert doc["params"]["require_different_mechanism"]["default"] is True
    assert "instrument-not-independent" in doc["failure_policy"]["classify_as"]


def check_each_surface_declares_both_instruments(doc: Mapping[str, Any]) -> None:
    props = doc["params"]["counting_surfaces"]["items"]["properties"]
    for field in (
        "reported_count_locator",
        "primary_instrument",
        "independent_instrument",
        "population_definition",
    ):
        assert field in props, f"a surface with no {field!r} cannot be audited"
    assert doc["params"]["counting_surfaces"]["min_items"] >= 1


def check_the_counter_cannot_read_the_reported_figure_first(
    doc: Mapping[str, Any],
) -> None:
    body = {str(st["id"]): st for st in K.fanout(doc, "audit-surfaces")["body"]}
    assert set(body) == {
        "read-reported",
        "count-independently",
        "compare-and-verdict",
    }, f"the per-surface pipeline changed shape: {sorted(body)}"
    assert "read-reported" not in (
        body["count-independently"].get("depends_on") or []
    ), "an independent count that waits on the reported figure is anchored to it"
    assert set(body["compare-and-verdict"].get("depends_on") or []) == {
        "read-reported",
        "count-independently",
    }, "the comparison is the only stage entitled to see both numbers"


def check_the_reader_and_the_counter_are_separate_roles(doc: Mapping[str, Any]) -> None:
    body = {str(st["id"]): st for st in K.fanout(doc, "audit-surfaces")["body"]}
    assert body["read-reported"]["role"] == "surface-reader"
    assert body["count-independently"]["role"] == "independent-counter"
    assert body["read-reported"]["role"] != body["count-independently"]["role"], (
        "one role holding both numbers is one instrument wearing two hats"
    )
    counter = doc["roles"]["independent-counter"]
    assert counter["authority"] == "veto"
    assert counter["independence"] == "independent"
    routes = K.routes_for(doc, "independent-counter")
    assert routes, "the adjudicating role must be pinned by a routing rule"


def check_the_population_must_be_defined_and_shared(doc: Mapping[str, Any]) -> None:
    spec = K.gate_for_stage(doc, "gate-population")
    assert "population_definition_present == true" in spec["expression"]
    assert "both_instruments_count_same_population == true" in spec["expression"], (
        "two counts of two populations measure scope, not truncation"
    )
    assert spec["blocking"] is True and spec["on_fail"] == "fail"
    assert "scope-mismatch" in doc["failure_policy"]["classify_as"]
    assert "scope-mismatch" in doc["retry_policy"]["no_retry_on"]


def check_disclosure_is_the_pass_condition_not_the_absence_of_caps(
    doc: Mapping[str, Any],
) -> None:
    spec = K.gate_for_stage(doc, "gate-disclosure")
    assert "truncated == false OR truncation_disclosed == true" in spec["expression"], (
        "a cap is legitimate; an UNDISCLOSED cap is the defect"
    )
    assert spec["on_fail"] == "repair", (
        "the remedy is to add the disclosure, not to abort"
    )
    pattern = doc["params"]["disclosure_pattern"]
    assert pattern["default"], "a disclosure standard with no shape cannot be checked"
    ids = {c["id"] for c in K.benchmark_cases(doc)}
    assert "disclosed-cap-passes" in ids, (
        "without this case the audit would read as 'all caps are defects'"
    )


def check_the_independent_counter_is_calibrated_first(doc: Mapping[str, Any]) -> None:
    cases = {c["id"]: c for c in K.benchmark_cases(doc)}
    assert "calibrate-the-counter" in cases, (
        "a counter that has never been calibrated cannot adjudicate another counter"
    )
    example = K.worked_examples(doc)[0]
    assert "calibration" in example, (
        "the worked example must record the calibration run"
    )
    assert any(ch.isdigit() for ch in str(example["calibration"])), (
        "a calibration with no known-size population named is not a calibration"
    )


def check_a_single_signal_verdict_is_never_retried(doc: Mapping[str, Any]) -> None:
    no_retry = set(doc["retry_policy"]["no_retry_on"])
    assert "verdict-on-one-signal" in no_retry, (
        "a one-signal verdict is a category error, not a transient failure"
    )
    assert "assertion-passes-prefix" in no_retry
    assert "instrument-not-independent" in doc["retry_policy"]["retry_on"], (
        "a non-independent instrument CAN be swapped and retried; that is the repairable case"
    )


def check_an_unverifiable_surface_is_never_folded_into_a_pass(
    doc: Mapping[str, Any],
) -> None:
    rule = K.stopping_rule(doc, "unverifiable-surface")
    assert "unverifiable_surfaces > 0" in rule["expression"]
    assert rule["on_stop"] == "emit-partial", (
        "an unverifiable surface makes the run partial, never complete"
    )
    assert "unverifiable" in doc["failure_policy"]["classify_as"]
    complete = K.stopping_rule(doc, "every-surface-audited")
    assert "surfaces_verdicted == surfaces_declared" in complete["expression"]
    assert "instruments_share_mechanism == false" in complete["minimum_conditions"]


def check_the_auditor_cannot_edit_the_schemas(doc: Mapping[str, Any]) -> None:
    policy = doc["tool_policy"]
    assert policy["default"] == "deny"
    assert policy["network"] == "none"
    assert "platform/schema/**" in policy["forbid_write_paths"], (
        "an auditor that can rewrite the contracts can make any count conform"
    )
    assert policy["write_paths"] == ["command-center/truncation/**"]


def check_the_audit_is_byte_reproducible(doc: Mapping[str, Any]) -> None:
    replay = doc["replay"]
    assert replay["deterministic"] is True
    assert replay["verify"] == "hash-equal"
    forbidden = set(replay["forbid_nondeterministic_sources"])
    assert {"clock", "random", "network"} <= forbidden
    assert doc["cache"]["enabled"] is False, (
        "a cached count is the stale-figure defect this workflow audits"
    )


def check_the_barrier_requires_a_verdict_per_surface(doc: Mapping[str, Any]) -> None:
    spec = K.barrier(doc, "audit-surfaces")
    K.assert_rejects_fire_and_forget(spec)
    assert "compare-and-verdict" in spec["require_stages"], (
        "requiring only the reads would let a surface finish with two numbers and no verdict"
    )
    assert spec["mode"] == "all"
    assert spec["on_partial"] == "proceed-with-quarantine"


def check_the_worked_example_contains_a_clean_row(doc: Mapping[str, Any]) -> None:
    results = K.worked_examples(doc)[0]["results"]
    verdicts = {row["verdict"] for row in results}
    assert "CLEAN" in verdicts, (
        "a detector that has never returned CLEAN is indistinguishable from one that always alarms"
    )
    assert "UNDISCLOSED-TRUNCATION" in verdicts, (
        "the example must also show a real finding"
    )
    for row in results:
        assert row["mechanical_difference"], (
            "every audited row must name HOW the two instruments differ"
        )
        assert row["reported"] is not None and row["actual"] is not None
    finding = next(r for r in results if r["verdict"] == "UNDISCLOSED-TRUNCATION")
    assert finding["actual"] > finding["reported"], (
        "a floor-presented-as-total finding must show the floor below the true total"
    )
    assert finding["assertion_added"], (
        "a finding must ship the regression assertion for it"
    )


ALL_CHECKS = (
    check_the_second_instrument_must_be_mechanically_different,
    check_each_surface_declares_both_instruments,
    check_the_counter_cannot_read_the_reported_figure_first,
    check_the_reader_and_the_counter_are_separate_roles,
    check_the_population_must_be_defined_and_shared,
    check_disclosure_is_the_pass_condition_not_the_absence_of_caps,
    check_the_independent_counter_is_calibrated_first,
    check_a_single_signal_verdict_is_never_retried,
    check_an_unverifiable_surface_is_never_folded_into_a_pass,
    check_the_auditor_cannot_edit_the_schemas,
    check_the_audit_is_byte_reproducible,
    check_the_barrier_requires_a_verdict_per_surface,
    check_the_worked_example_contains_a_clean_row,
)


@pytest.mark.parametrize("check", ALL_CHECKS, ids=lambda c: c.__name__)
def test_shipped_blueprint_satisfies_every_mechanism_check(check: Any) -> None:
    check(DOC)


def test_shipped_blueprint_is_conformant() -> None:
    assert K.schema_errors(DOC) == []
    assert K.semantic_violations(DOC) == []
    assert K.blueprint_meta(DOC)["slot"] == 94
    assert K.blueprint_meta(DOC)["design_card"] == "BP-MNT-03"
    assert DOC["flagship"] is True


# ------------------------------------------------------------------------- mutation controls


def _accept_the_same_instrument_twice(doc: dict) -> None:
    doc["gates"]["second-instrument-is-different"]["expression"] = (
        "surfaces_verdicted > 0"
    )


def _drop_the_independent_instrument_field(doc: dict) -> None:
    doc["params"]["counting_surfaces"]["items"]["properties"].pop(
        "independent_instrument"
    )


def _let_the_counter_wait_on_the_reported_figure(doc: dict) -> None:
    fan = K.find_stage_mut(doc, "audit-surfaces")
    for st in fan["body"]:
        if st["id"] == "count-independently":
            st["depends_on"] = ["read-reported"]


def _give_both_numbers_to_one_role(doc: dict) -> None:
    fan = K.find_stage_mut(doc, "audit-surfaces")
    for st in fan["body"]:
        if st["id"] == "count-independently":
            st["role"] = "surface-reader"


def _drop_the_shared_population_requirement(doc: dict) -> None:
    doc["gates"]["population-defined"]["expression"] = (
        "population_definition_present == true"
    )


def _treat_every_cap_as_a_defect(doc: dict) -> None:
    doc["gates"]["disclosure-is-the-standard"]["expression"] = "truncated == false"


def _drop_the_calibration_case(doc: dict) -> None:
    doc["x_extensions"]["benchmark_cases"] = [
        c
        for c in doc["x_extensions"]["benchmark_cases"]
        if c["id"] != "calibrate-the-counter"
    ]


def _retry_a_one_signal_verdict(doc: dict) -> None:
    doc["retry_policy"]["no_retry_on"] = ["scope-mismatch"]


def _complete_on_an_unverifiable_surface(doc: dict) -> None:
    for rule in doc["stopping_rules"]:
        if rule["id"] == "unverifiable-surface":
            rule["on_stop"] = "complete"


def _allow_schema_writes(doc: dict) -> None:
    doc["tool_policy"]["forbid_write_paths"] = ["command-center/WORK-UNIT-CATALOG.json"]


def _enable_the_cache(doc: dict) -> None:
    doc["cache"]["enabled"] = True


def _require_only_the_reads_at_the_barrier(doc: dict) -> None:
    K.find_stage_mut(doc, "audit-surfaces")["barrier"]["require_stages"] = [
        "read-reported"
    ]


def _delete_the_clean_row_from_the_example(doc: dict) -> None:
    example = doc["x_extensions"]["worked_examples"][0]
    example["results"] = [r for r in example["results"] if r["verdict"] != "CLEAN"]


MUTATIONS = (
    (
        check_the_second_instrument_must_be_mechanically_different,
        _accept_the_same_instrument_twice,
    ),
    (
        check_each_surface_declares_both_instruments,
        _drop_the_independent_instrument_field,
    ),
    (
        check_the_counter_cannot_read_the_reported_figure_first,
        _let_the_counter_wait_on_the_reported_figure,
    ),
    (
        check_the_reader_and_the_counter_are_separate_roles,
        _give_both_numbers_to_one_role,
    ),
    (
        check_the_population_must_be_defined_and_shared,
        _drop_the_shared_population_requirement,
    ),
    (
        check_disclosure_is_the_pass_condition_not_the_absence_of_caps,
        _treat_every_cap_as_a_defect,
    ),
    (check_the_independent_counter_is_calibrated_first, _drop_the_calibration_case),
    (check_a_single_signal_verdict_is_never_retried, _retry_a_one_signal_verdict),
    (
        check_an_unverifiable_surface_is_never_folded_into_a_pass,
        _complete_on_an_unverifiable_surface,
    ),
    (check_the_auditor_cannot_edit_the_schemas, _allow_schema_writes),
    (check_the_audit_is_byte_reproducible, _enable_the_cache),
    (
        check_the_barrier_requires_a_verdict_per_surface,
        _require_only_the_reads_at_the_barrier,
    ),
    (
        check_the_worked_example_contains_a_clean_row,
        _delete_the_clean_row_from_the_example,
    ),
)


@pytest.mark.parametrize(
    "check,mutate", MUTATIONS, ids=lambda v: getattr(v, "__name__", "")
)
def test_each_check_fails_on_its_mutated_blueprint(check: Any, mutate: Any) -> None:
    broken = K.mutant(DOC, mutate)
    assert K.raises_assertion(check, broken), (
        f"{check.__name__} stayed silent on the mutated blueprint, so it measures nothing"
    )


def test_the_anchored_counter_mutant_is_schema_legal() -> None:
    """The anchoring defect in its exact shape: a legal dependency edge that destroys independence."""
    broken = K.mutant(DOC, _let_the_counter_wait_on_the_reported_figure)
    assert K.schema_errors(broken) == []
    assert K.semantic_violations(broken) == []
    assert K.raises_assertion(
        check_the_counter_cannot_read_the_reported_figure_first, broken
    )
