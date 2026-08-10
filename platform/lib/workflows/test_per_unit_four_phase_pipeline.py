"""FLAGSHIP end-to-end test for `per-unit-four-phase-pipeline` (bp-4, doc-order 38, BP-IMP-01).

The mechanism claim under test is an ABSENCE: the fan-out declares no barrier, because a
cohort-wide phase barrier is the measured deadlock cause the blueprint exists to remove. An
absence is exactly the kind of property a green test can fake, so every check below is paired
with a mutation that must make it fail.
"""

from __future__ import annotations

from typing import Any, Mapping

import bp4_testkit as K
import pytest

WORKFLOW_ID = "per-unit-four-phase-pipeline"
DOC = K.load(WORKFLOW_ID)

FANOUT = "unit-pipelines"
FOUR_PHASES = ("implement", "validate", "adversarial-review", "commit")


# ------------------------------------------------------------------------------- the checks


def check_no_cohort_barrier(doc: Mapping[str, Any]) -> None:
    """THE distinctive property: the unit fan-out must not declare a barrier."""
    fanout = K.stage(doc, FANOUT)
    assert fanout["kind"] == "fanout"
    assert "barrier" not in fanout, (
        "a barrier on the unit fan-out reintroduces the cohort-wide wait this blueprint removes"
    )
    assert fanout.get("on_item_failure") == "continue", (
        "a unit must not be able to abort or hold its siblings"
    )


def check_four_phases_are_ordered_inside_one_unit(doc: Mapping[str, Any]) -> None:
    """The four phases live in the fan-out BODY, chained by depends_on, not across units."""
    body = {st["id"]: st for st in K.stage(doc, FANOUT)["body"]}
    for phase in FOUR_PHASES:
        assert phase in body, f"phase {phase!r} is not inside the per-unit body"
    assert "depends_on" not in body["implement"], (
        "IMPLEMENT is the head of the per-unit chain"
    )
    chain = {
        "validate": "implement",
        "coverage-gate": "validate",
        "adversarial-review": "coverage-gate",
        "self-certification-gate": "adversarial-review",
        "completion-gate": "self-certification-gate",
        "commit": "completion-gate",
    }
    for later, earlier in chain.items():
        assert body[later].get("depends_on") == [earlier], (
            f"{later} must depend on {earlier} so the phases cannot be reordered"
        )


def check_reviewer_is_fresh_and_cross_vendor(doc: Mapping[str, Any]) -> None:
    implementer = doc["roles"]["implementer"]
    reviewer = doc["roles"]["reviewer"]
    assert reviewer["vendor"] != implementer["vendor"], (
        "review must not share the author's vendor"
    )
    assert reviewer.get("cross_vendor_required") is True
    assert reviewer.get("authority") == "veto", (
        "a reviewer that cannot block is decoration"
    )
    expression = K.gate(doc, "no-self-certification")["expression"]
    for clause in (
        "reviewer_agent_id != implementer_agent_id",
        "reviewer_vendor != implementer_vendor",
    ):
        assert clause in expression, (
            f"the self-certification gate does not assert {clause!r}"
        )


def check_coverage_comes_from_the_project_ssot(doc: Mapping[str, Any]) -> None:
    gate = K.gate(doc, "coverage-ssot")
    assert gate["predicate"] == "coverage-threshold"
    assert gate["blocking"] is True
    assert "thresholds_file_found == true" in gate["expression"]
    assert "coverage_meets_ssot == true" in gate["expression"]
    not_checked = K.gate(doc, "coverage-not-checked")
    assert not_checked["blocking"] is False
    assert "not_checked_emitted == true" in not_checked["expression"], (
        "a project without a thresholds file must emit NOT-CHECKED, never a silent pass"
    )
    assert "coverage_thresholds_path" in doc["params"]


def check_completion_predicate_requires_all_twelve_conditions(
    doc: Mapping[str, Any],
) -> None:
    gate = K.gate(doc, "unit-complete")
    assert gate["predicate"] == "completion-predicate-v1"
    assert gate["conditions_required"] == list(range(1, 13)), (
        "the shared predicate is all twelve conditions; a subset is a different predicate"
    )
    assert gate["blocking"] is True and gate["evidence_required"] is True


def check_two_strikes_then_redecomposition(doc: Mapping[str, Any]) -> None:
    repair = K.stage(doc, "unit-repair")
    assert repair["kind"] == "repair_loop"
    assert repair["max_attempts"] == 2, (
        "a third attempt on the same decomposition is not offered"
    )
    assert repair["target"] == [FANOUT]
    assert repair["require_root_cause"] is True
    verify = repair["verify"]["gate"]
    assert "verifier_agent_id != repairer_agent_id" in verify["expression"], (
        "the repair must not be certified by whoever applied it"
    )
    pivot = doc["retry_policy"]["pivot"]
    assert pivot["after_attempts"] == 2 and pivot["enumerate_alternatives_min"] >= 2


def check_hook_bypass_is_denied_by_policy(doc: Mapping[str, Any]) -> None:
    denied = set(doc["tool_policy"]["deny"])
    assert {"Bash:git-no-verify", "Bash:git-push-force"} <= denied, (
        "--no-verify and force-push must be denied by policy, not by convention"
    )


ALL_CHECKS = (
    check_no_cohort_barrier,
    check_four_phases_are_ordered_inside_one_unit,
    check_reviewer_is_fresh_and_cross_vendor,
    check_coverage_comes_from_the_project_ssot,
    check_completion_predicate_requires_all_twelve_conditions,
    check_two_strikes_then_redecomposition,
    check_hook_bypass_is_denied_by_policy,
)


# --------------------------------------------------------------------- healthy state: all pass


@pytest.mark.parametrize("check", ALL_CHECKS, ids=lambda c: c.__name__)
def test_shipped_blueprint_satisfies_every_mechanism_check(check: Any) -> None:
    check(DOC)


def test_shipped_blueprint_is_conformant() -> None:
    assert K.schema_errors(DOC) == []
    assert K.semantic_violations(DOC) == []


# ------------------------------------------------------ broken state: each check must FIRE once


def _add_cohort_barrier(doc: dict) -> None:
    K.find_stage_mut(doc, FANOUT)["barrier"] = {"mode": "all", "on_partial": "fail"}


def _reorder_phases(doc: dict) -> None:
    K.find_stage_mut(doc, "commit")["depends_on"] = ["validate"]


def _make_reviewer_same_vendor(doc: dict) -> None:
    doc["roles"]["reviewer"]["vendor"] = doc["roles"]["implementer"]["vendor"]


def _let_coverage_pass_without_the_ssot(doc: dict) -> None:
    doc["gates"]["coverage-ssot"]["expression"] = "tests_passed == true"


def _drop_a_predicate_condition(doc: dict) -> None:
    doc["gates"]["unit-complete"]["conditions_required"] = list(range(1, 12))


def _allow_a_third_attempt(doc: dict) -> None:
    K.find_stage_mut(doc, "unit-repair")["max_attempts"] = 3


def _permit_no_verify(doc: dict) -> None:
    doc["tool_policy"]["deny"] = ["WebFetch"]


MUTATIONS = (
    (check_no_cohort_barrier, _add_cohort_barrier),
    (check_four_phases_are_ordered_inside_one_unit, _reorder_phases),
    (check_reviewer_is_fresh_and_cross_vendor, _make_reviewer_same_vendor),
    (check_coverage_comes_from_the_project_ssot, _let_coverage_pass_without_the_ssot),
    (
        check_completion_predicate_requires_all_twelve_conditions,
        _drop_a_predicate_condition,
    ),
    (check_two_strikes_then_redecomposition, _allow_a_third_attempt),
    (check_hook_bypass_is_denied_by_policy, _permit_no_verify),
)


@pytest.mark.parametrize(
    "check,mutate", MUTATIONS, ids=lambda v: getattr(v, "__name__", "")
)
def test_each_check_fails_on_its_mutated_blueprint(check: Any, mutate: Any) -> None:
    """The both-states control: every check above is proven able to fail."""
    broken = K.mutant(DOC, mutate)
    assert K.raises_assertion(check, broken), (
        f"{check.__name__} stayed silent on the mutated blueprint, so it measures nothing"
    )


def test_the_barrier_mutation_is_otherwise_legal() -> None:
    """The mutation must be caught by THIS test, not by the schema.

    If adding a barrier were a schema error, the absence would already be enforced elsewhere and
    this flagship test would be redundant. It is not: a barrier on a fan-out is perfectly valid
    DSL, which is exactly why the property needs a test of its own.
    """
    broken = K.mutant(DOC, _add_cohort_barrier)
    assert K.schema_errors(broken) == []
    assert K.semantic_violations(broken) == []
    assert K.raises_assertion(check_no_cohort_barrier, broken)
