"""End-to-end tests for BP-SEC-06 (card 66), the fetched-content injection and egress review.

Mechanism under test: a computed source-to-sink REACHABILITY CLOSURE plus a per-payload
DEFENCE-IN-DEPTH gate that requires two independent facts - the payload was not executed AND
the guard would have blocked the privileged action anyway. A behavioural excuse ("the model
would not comply") is counted and must be zero.
"""

from __future__ import annotations

import pytest

import _harness as H

NAME = "fetched-content-injection-egress-review"


@pytest.fixture(scope="module")
def doc() -> dict:
    return H.load(NAME)


def test_schema_and_semantics_are_clean(doc: dict) -> None:
    assert H.conformance_failures(doc) == []


def test_inline_units_pass_normative_and_strict(doc: dict) -> None:
    assert H.inline_units(doc)
    assert H.unit_profile_failures(doc, "normative") == []
    assert H.unit_profile_failures(doc, "strict") == []


def test_sentinels_name_their_own_units(doc: dict) -> None:
    assert H.sentinel_violations(doc) == []


def test_worked_example_conforms(doc: dict) -> None:
    assert H.worked_example_failures(doc) == []


def test_worked_example_checker_fires_on_a_dropped_binding(doc: dict) -> None:
    fails = H.worked_example_failures(H.mutated(doc, H.drop_a_required_binding))
    assert any("has no value in the worked example" in f for f in fails), fails


def test_worked_example_checker_fires_on_an_unaccounted_top_level_stage(
    doc: dict,
) -> None:
    def bend(d: dict) -> None:
        ex = d["x_extensions"]["worked_example"]
        ex["expected_stage_path"] = [
            s for s in ex["expected_stage_path"] if s != "trace-reachability"
        ]

    fails = H.worked_example_failures(H.mutated(doc, bend))
    assert any("neither walked nor skipped" in f for f in fails), fails


# ------------------------------------------------------- mechanism: closure, not eyeballing


def test_reachability_is_a_computed_transitive_closure(doc: dict) -> None:
    unit = H.stage(doc, "trace-reachability")["work_unit"]
    target = unit["question_or_target"]
    assert "graph closure rather than by judgement" in target
    assert "SEVERED or UNSEVERED" in target
    ev = unit["evidence_requirement"]
    assert "every intermediate hop" in ev, "a pair without its path cannot be audited"
    tests = " ".join(unit["tests_required"])
    assert "two-hop path" in tests, "a one-hop trace is the known incomplete closure"
    assert "specificity control" in tests


def test_the_enumeration_gate_precedes_the_closure(doc: dict) -> None:
    order = H.top_level_stage_ids(doc)
    assert order.index("map-sources-and-sinks") < order.index("enumeration-gate")
    assert order.index("enumeration-gate") < order.index("trace-reachability")
    expr = H.gate_expressions(doc)["capability-enumeration-complete"]
    assert "sinks_enumerated == sinks_requested" in expr
    assert "dynamic_tool_sets_disclosed == true" in expr, (
        "a dynamic tool set makes the enumeration a floor; that must be declared, not hidden"
    )


# ------------------------------------------------- mechanism: two independent defences per payload


def test_the_defence_in_depth_gate_requires_two_independent_facts(doc: dict) -> None:
    expr = H.gate_expressions(doc)["defence-in-depth"]
    assert "payload_executed == false" in expr
    assert "guard_would_have_blocked == true" in expr
    assert " AND " in expr, "either fact alone is a single signal"
    gate_stage = H.stage(doc, "defence-in-depth-gate")
    assert gate_stage["gate_ref"] == "defence-in-depth"
    assert gate_stage["depends_on"] == ["run-one-payload"]


def test_the_probe_records_both_facts_from_independent_observations(doc: dict) -> None:
    unit = H.stage(doc, "run-one-payload")["work_unit"]
    assert "TWO independent facts" in unit["question_or_target"]
    assert "two mechanically independent readings" in unit["evidence_requirement"]
    tests = " ".join(unit["tests_required"])
    assert "must be shown able to detect a real failure" in tests, (
        "a probe that can only report success is not a detector"
    )
    assert "removing the guard must flip" in tests, (
        "the second defence needs its own control"
    )
    assert "probe-single-signal" in unit["failure_classification"]


def test_reducing_the_gate_to_one_defence_is_detectable(doc: dict) -> None:
    def bend(d: dict) -> None:
        d["gates"]["defence-in-depth"]["expression"] = "payload_executed == false"

    mutant = H.mutated(doc, bend)
    assert H.conformance_failures(mutant) == []
    assert (
        "guard_would_have_blocked" not in H.gate_expressions(mutant)["defence-in-depth"]
    )


def test_the_probe_runs_in_a_container_with_no_network(doc: dict) -> None:
    unit = H.stage(doc, "run-one-payload")["work_unit"]
    assert unit["execution_substrate"] == "container"
    assert doc["tool_policy"]["network"] == "none"
    for banned in ("WebFetch", "WebSearch", "mcp__search-hub__web_search_exa"):
        assert banned in doc["tool_policy"]["deny"], banned
    assert "sandbox-escape" in doc["retry_policy"]["no_retry_on"]


# ------------------------------------------- mechanism: a behavioural excuse is not a mitigation


def test_behavioural_excuses_are_counted_and_must_be_zero(doc: dict) -> None:
    expr = H.gate_expressions(doc)["no-unsevered-path"]
    assert "reachable_paths_without_sever == 0" in expr
    assert "behavioural_excuses_accepted == 0" in expr
    unit = H.stage(doc, "propose-mitigations")["work_unit"]
    assert "behavioural excuse" in unit["question_or_target"]
    assert "behavioural-excuse" in unit["failure_classification"]
    assert "behavioural-excuse" in doc["retry_policy"]["no_retry_on"]
    tests = " ".join(unit["tests_required"])
    assert "coverage control" in tests, (
        "every unsevered path needs exactly one mitigation"
    )


def test_the_reviewer_is_cross_vendor_from_the_tracer(doc: dict) -> None:
    tracer = doc["roles"]["capability-tracer"]
    reviewer = doc["roles"]["architecture-reviewer"]
    assert reviewer["vendor"] != tracer["vendor"]
    assert reviewer["cross_vendor_required"] is True
    assert reviewer["authority"] == "veto"
    route = doc["model_routing"]["routes"][0]
    assert route["when"] == "stage_role == architecture-reviewer"
    assert route["target"]["vendor"] == reviewer["vendor"]


def test_an_executed_payload_escalates_rather_than_completing(doc: dict) -> None:
    rules = {r["id"]: r for r in doc["stopping_rules"]}
    assert rules["probe-showed-execution"]["expression"] == "payload_executed == true"
    assert rules["probe-showed-execution"]["on_stop"] == "escalate"
    assert doc["failure_policy"]["on_failure"] == "escalate-to-human"
