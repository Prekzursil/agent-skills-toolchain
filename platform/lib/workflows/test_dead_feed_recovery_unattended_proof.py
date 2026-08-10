"""End-to-end tests for BP-INC-02 (card 68), dead-feed recovery gated on an unattended hit.

Mechanism under test: the acceptance criterion is an event NOBODY IN THIS WORKFLOW CAUSED. The
manual rebuild is explicitly disqualified as proof, the loop converges on an externally-caused
observation, and - uniquely in this set - it FAILS rather than emitting a partial when the metric
never moves. Environmental-versus-defect separation is delegated, not re-implemented.
"""

from __future__ import annotations

import pytest

import _harness as H

NAME = "dead-feed-recovery-unattended-proof"


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


def test_worked_example_checker_fires_on_an_out_of_range_value(doc: dict) -> None:
    def bend(d: dict) -> None:
        d["x_extensions"]["worked_example"]["params"]["expected_cadence_seconds"] = 5

    fails = H.worked_example_failures(H.mutated(doc, bend))
    assert any("below its declared minimum" in f for f in fails), fails


# ------------------------------------------------ mechanism: staleness is arithmetic, not feeling


def test_staleness_is_measured_against_a_declared_cadence(doc: dict) -> None:
    assert doc["params"]["expected_cadence_seconds"]["required"] is True
    unit = H.stage(doc, "measure-staleness")["work_unit"]
    assert "ratio to expected_cadence_seconds" in unit["question_or_target"]
    assert "four numbers" in unit["evidence_requirement"]
    tests = " ".join(unit["tests_required"])
    assert "known-broken half" in tests and "known-good half" in tests, (
        "a staleness detector needs both halves or it cannot separate stale from healthy"
    )
    assert "cadence-undeclared" in unit["failure_classification"]


# -------------------------------------------- mechanism: delegation, not re-implementation


def test_environmental_separation_is_delegated_to_the_triage_blueprint(doc: dict) -> None:
    st = H.stage(doc, "separate-environmental-cause")
    assert st["kind"] == "subworkflow"
    ref = st["workflow"]["workflow_id"]
    assert ref == "live-estate-incident-triage"
    declared = doc["subworkflows"][ref]
    assert declared["source"] == f"platform/workflows/{ref}.json"
    child = H.load(ref)
    assert child["id"] == ref
    assert H.conformance_failures(child) == []
    assert st["propagate_failure"] is True
    assert st["params"]["allow_disruptive_actions"] is False, (
        "the delegated triage must not be handed authority to restart the producer"
    )


def test_a_subworkflow_reference_to_an_undeclared_child_is_caught(doc: dict) -> None:
    def bend(d: dict) -> None:
        for s in d["stages"]:
            if s["id"] == "separate-environmental-cause":
                s["workflow"]["workflow_id"] = "no-such-child"

    violations = H.semantic_violations(H.mutated(doc, bend))
    assert any("DSL-SEM-006" in v for v in violations), violations


# ------------------------------------- mechanism: only an UNATTENDED write counts as proof


def test_the_manual_rebuild_is_explicitly_disqualified_as_proof(doc: dict) -> None:
    expr = H.gate_expressions(doc)["unattended-write-observed"]
    assert "unattended_writes_observed >= 1" in expr
    assert "manual_rebuild_counted_as_proof == false" in expr
    order = H.top_level_stage_ids(doc)
    assert order.index("manual-rebuild") < order.index("await-unattended-hit")
    assert order.index("await-unattended-hit") < order.index("unattended-gate")
    assert "NOT the proof" in H.stage(doc, "manual-rebuild")["title"]


def test_attribution_requires_a_negative_not_just_a_timestamp(doc: dict) -> None:
    unit = H.stage(doc, "poll-for-unattended-write")["work_unit"]
    ev = unit["evidence_requirement"]
    assert "two timestamps and a negative" in ev
    assert "absence of any workflow action" in ev
    tests = " ".join(unit["tests_required"])
    assert "must NOT count as unattended" in tests, "the attribution control must exist"
    assert "forensically silent" in tests, (
        "a killed producer leaves no error, so absence of an error is not absence of failure"
    )
    assert "attribution-ambiguous" in unit["failure_classification"]
    assert "attribution-ambiguous" in doc["retry_policy"]["no_retry_on"]


def test_the_wait_loop_fails_rather_than_emitting_a_partial(doc: dict) -> None:
    loop = H.stage(doc, "await-unattended-hit")
    conv = loop["convergence"]
    assert loop["kind"] == "loop"
    assert conv["converged_when"] == "unattended_writes_observed >= 1"
    assert {m["name"] for m in conv["metrics"]} == {"unattended_writes_observed"}
    assert conv["on_no_convergence"] == "fail", (
        "an unattended hit that never arrives means the FIX failed; emitting a partial would "
        "close the incident on the manual rebuild, which is the defect this blueprint prevents"
    )
    assert conv["max_iterations"] <= 12


def test_the_convergence_metric_must_stay_declared(doc: dict) -> None:
    def bend(d: dict) -> None:
        for s in d["stages"]:
            if s["id"] == "await-unattended-hit":
                s["convergence"]["metrics"] = [{"name": "something_else", "direction": "increase"}]

    violations = H.semantic_violations(H.mutated(doc, bend))
    assert any("DSL-SEM-008" in v for v in violations), violations


def test_flipping_on_no_convergence_to_emit_partial_is_detectable(doc: dict) -> None:
    def bend(d: dict) -> None:
        for s in d["stages"]:
            if s["id"] == "await-unattended-hit":
                s["convergence"]["on_no_convergence"] = "emit-partial"

    mutant = H.mutated(doc, bend)
    assert H.conformance_failures(mutant) == [], "still schema-valid; the loss is semantic"
    assert H.stage(mutant, "await-unattended-hit")["convergence"]["on_no_convergence"] == (
        "emit-partial"
    )


# ------------------------------------------------------- mechanism: leave a self-report behind


def test_a_freshness_postcondition_is_left_behind_by_default(doc: dict) -> None:
    assert doc["params"]["add_freshness_postcondition"]["default"] is True
    st = H.stage(doc, "leave-freshness-postcondition")
    assert st["when"] == "add_freshness_postcondition == true"
    assert "command-center/incident/feed/freshness-postcondition.json" in H.declared_paths(doc)


def test_the_producer_is_fixed_at_its_repo_source_not_a_deployed_copy(doc: dict) -> None:
    unit = H.stage(doc, "fix-producer")["work_unit"]
    assert "REPO source" in unit["question_or_target"]
    assert "deployed-copy-edit" in unit["failure_classification"]
    assert "deployed-copy-edit" in doc["retry_policy"]["no_retry_on"]
    tests = " ".join(unit["tests_required"])
    assert "deployed copy must be rejected" in tests


def test_the_wall_clock_estimate_admits_it_is_dominated_by_waiting(doc: dict) -> None:
    est = doc["estimate"]
    assert est["wallclock_seconds"]["max"] >= 2592000 * 0.5
    assert "WAITING" in est["impact"]["blast_radius"]
