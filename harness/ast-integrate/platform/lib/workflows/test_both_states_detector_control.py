"""FLAGSHIP end-to-end test for `both-states-detector-control` (bp-4, doc-order 45, BP-DBG-02).

Mechanism claims under test: a fixture PAIR; ASYMMETRIC gates (not firing on the broken state is
fatal, an unconstructible broken state is UNVALIDATABLE rather than a pass); the same probe bytes
in both runs; brokenness proven WITHOUT the probe under test (no circular evidence); and a fully
deterministic verdict with no retry, because retrying a fixture is how a cosmetic one gets built.
"""

from __future__ import annotations

from typing import Any, Mapping

import bp4_testkit as K
import pytest

WORKFLOW_ID = "both-states-detector-control"
DOC = K.load(WORKFLOW_ID)


# ------------------------------------------------------------------------------- the checks


def check_a_fixture_pair_is_required(doc: Mapping[str, Any]) -> None:
    assert "broken_fixture" in doc["params"]
    assert "healthy_fixture" in doc["params"]
    unit = K.stage(doc, "construct-fixtures")["work_unit"]
    assert "healthy twin" in unit["question_or_target"]
    K.assert_precedes(K.top_level_stage_ids(doc), "run-on-broken", "run-on-healthy")


def check_failing_to_fire_on_broken_is_fatal(doc: Mapping[str, Any]) -> None:
    gate = K.gate(doc, "fires-on-broken")
    assert gate["blocking"] is True
    assert gate["on_fail"] == "fail", (
        "a probe that does not fire on the broken state measures nothing - it cannot be repaired past"
    )
    assert "probe_fired_on_broken == true" in gate["expression"]
    assert "fire_signal_matches_declared == true" in gate["expression"], (
        "the fire signal is declared up front so 'it fired' cannot be re-defined after the run"
    )
    assert "expected_fire_signal" in doc["params"]


def check_an_unconstructible_broken_state_is_unvalidatable_not_a_pass(
    doc: Mapping[str, Any],
) -> None:
    gate = K.gate(doc, "broken-fixture-exists")
    assert gate["blocking"] is False, (
        "no fixture is an honest verdict, not a hard failure"
    )
    assert gate["on_fail"] == "record-and-continue"
    rule = next(r for r in doc["stopping_rules"] if r["id"] == "verdict-unvalidatable")
    assert rule["expression"] == "broken_fixture_constructed == false"
    assert rule["on_stop"] == "emit-partial", "UNVALIDATABLE must not read as complete"
    assert "unconstructible-broken-state" in doc["failure_policy"]["classify_as"]


def check_the_two_gates_are_asymmetric(doc: Mapping[str, Any]) -> None:
    """The asymmetry IS the mechanism: fixture-absence is soft, non-firing is fatal."""
    soft = K.gate(doc, "broken-fixture-exists")
    hard = K.gate(doc, "fires-on-broken")
    assert soft["blocking"] != hard["blocking"]
    assert (soft["on_fail"], hard["on_fail"]) == ("record-and-continue", "fail")


def check_both_runs_used_the_same_probe_bytes(doc: Mapping[str, Any]) -> None:
    gate = K.gate(doc, "probe-unmodified")
    assert "probe_bytes_unchanged_across_both_runs == true" in gate["expression"]
    assert gate["blocking"] is True
    assert "Edit" in doc["tool_policy"]["deny"], (
        "the probe under test must not be editable"
    )


def check_brokenness_is_proven_without_the_probe(doc: Mapping[str, Any]) -> None:
    unit = K.stage(doc, "construct-fixtures")["work_unit"]
    assert "INDEPENDENT" in unit["evidence_requirement"]
    assert "does not use the probe under test" in unit["evidence_requirement"]
    assert any("circular" in t for t in unit["tests_required"]), (
        "using the probe to prove its own fixture is the circularity this must exclude"
    )
    assert "circular-evidence" in unit["failure_classification"]


def check_the_verdict_is_deterministic_and_unretried(doc: Mapping[str, Any]) -> None:
    replay = doc["replay"]
    assert replay["deterministic"] is True
    assert replay["verify"] == "hash-equal"
    assert replay["on_divergence"] == "fail"
    assert set(replay["forbid_nondeterministic_sources"]) >= {
        "clock",
        "random",
        "network",
    }
    assert doc["retry_policy"]["strategy"] == "none"
    assert doc["retry_policy"]["max_attempts"] == 1
    assert doc["resume"]["enabled"] is False


def check_all_three_verdicts_are_reachable(doc: Mapping[str, Any]) -> None:
    ids = {rule["id"] for rule in doc["stopping_rules"]}
    assert ids == {
        "verdict-valid",
        "verdict-measures-nothing",
        "verdict-unvalidatable",
    }, "a control with only a VALID verdict cannot report the failure it exists to find"


ALL_CHECKS = (
    check_a_fixture_pair_is_required,
    check_failing_to_fire_on_broken_is_fatal,
    check_an_unconstructible_broken_state_is_unvalidatable_not_a_pass,
    check_the_two_gates_are_asymmetric,
    check_both_runs_used_the_same_probe_bytes,
    check_brokenness_is_proven_without_the_probe,
    check_the_verdict_is_deterministic_and_unretried,
    check_all_three_verdicts_are_reachable,
)


@pytest.mark.parametrize("check", ALL_CHECKS, ids=lambda c: c.__name__)
def test_shipped_blueprint_satisfies_every_mechanism_check(check: Any) -> None:
    check(DOC)


def test_shipped_blueprint_is_conformant() -> None:
    assert K.schema_errors(DOC) == []
    assert K.semantic_violations(DOC) == []


# ------------------------------------------------------------------------- mutation controls


def _drop_the_healthy_fixture(doc: dict) -> None:
    doc["params"].pop("healthy_fixture")


def _make_non_firing_recoverable(doc: dict) -> None:
    doc["gates"]["fires-on-broken"]["on_fail"] = "retry"


def _turn_unvalidatable_into_a_pass(doc: dict) -> None:
    for rule in doc["stopping_rules"]:
        if rule["id"] == "verdict-unvalidatable":
            rule["on_stop"] = "complete"


def _make_both_gates_hard(doc: dict) -> None:
    doc["gates"]["broken-fixture-exists"]["blocking"] = True
    doc["gates"]["broken-fixture-exists"]["on_fail"] = "fail"


def _allow_editing_the_probe(doc: dict) -> None:
    doc["tool_policy"]["deny"] = ["WebFetch", "WebSearch"]
    doc["gates"]["probe-unmodified"]["expression"] = "run_completed == true"


def _let_the_probe_prove_its_own_fixture(doc: dict) -> None:
    unit = K.find_stage_mut(doc, "construct-fixtures")["work_unit"]
    unit["evidence_requirement"] = (
        "the probe reports the fixture as broken, which is sufficient"
    )
    unit["tests_required"] = ["the two fixtures differ", "the broken one is broken"]


def _make_the_verdict_nondeterministic(doc: dict) -> None:
    doc["replay"]["deterministic"] = False
    doc["replay"].pop("seed", None)


def _keep_only_the_valid_verdict(doc: dict) -> None:
    doc["stopping_rules"] = [
        r for r in doc["stopping_rules"] if r["id"] == "verdict-valid"
    ]


MUTATIONS = (
    (check_a_fixture_pair_is_required, _drop_the_healthy_fixture),
    (check_failing_to_fire_on_broken_is_fatal, _make_non_firing_recoverable),
    (
        check_an_unconstructible_broken_state_is_unvalidatable_not_a_pass,
        _turn_unvalidatable_into_a_pass,
    ),
    (check_the_two_gates_are_asymmetric, _make_both_gates_hard),
    (check_both_runs_used_the_same_probe_bytes, _allow_editing_the_probe),
    (
        check_brokenness_is_proven_without_the_probe,
        _let_the_probe_prove_its_own_fixture,
    ),
    (
        check_the_verdict_is_deterministic_and_unretried,
        _make_the_verdict_nondeterministic,
    ),
    (check_all_three_verdicts_are_reachable, _keep_only_the_valid_verdict),
)


@pytest.mark.parametrize(
    "check,mutate", MUTATIONS, ids=lambda v: getattr(v, "__name__", "")
)
def test_each_check_fails_on_its_mutated_blueprint(check: Any, mutate: Any) -> None:
    broken = K.mutant(DOC, mutate)
    assert K.raises_assertion(check, broken), (
        f"{check.__name__} stayed silent on the mutated blueprint, so it measures nothing"
    )


def test_the_deterministic_mutation_is_caught_by_the_schema_too() -> None:
    """A rare case where the DSL itself helps: dropping `seed` while claiming determinism.

    The mutation flips `deterministic` to false AND drops the seed, which is schema-legal, so
    this test records honestly that only the mechanism check catches it - the schema's allOf
    fires only when determinism is still CLAIMED.
    """
    broken = K.mutant(DOC, _make_the_verdict_nondeterministic)
    assert K.schema_errors(broken) == []

    def claim_without_seed(doc: dict) -> None:
        doc["replay"].pop("seed")

    still_claiming = K.mutant(DOC, claim_without_seed)
    assert K.schema_errors(still_claiming) != [], (
        "a deterministic replay with no seed must be a schema error"
    )
