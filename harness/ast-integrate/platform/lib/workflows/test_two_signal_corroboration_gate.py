"""FLAGSHIP end-to-end test for `two-signal-corroboration-gate` (bp-4, doc-order 46, BP-DBG-03).

Mechanism claims under test: the SOURCE probe is mandatory, non-empty and invocation-shaped (an
undeclared source is zero signals, not one - the measured hole in the shipped claim gate);
independence is asserted as a NAMED dimension and a re-run of the source does not count; the
disruptive action is not authorised on disagreement; and the human checkpoint fails on timeout so
a destructive act can never become authorised because nobody answered.
"""

from __future__ import annotations

from typing import Any, Mapping

import bp4_testkit as K
import pytest

WORKFLOW_ID = "two-signal-corroboration-gate"
DOC = K.load(WORKFLOW_ID)


# ------------------------------------------------------------------------------- the checks


def check_source_probe_is_a_required_nonempty_param(doc: Mapping[str, Any]) -> None:
    spec = doc["params"].get("source_probe")
    assert spec is not None, "the producing measurement must be a first-class parameter"
    assert spec.get("required") is True
    assert spec.get("min_length", 0) >= 1, (
        "an empty string must not satisfy the source probe"
    )
    assert "default" not in spec, "a defaulted source probe is an undeclared source"


def check_the_source_gate_is_blocking_and_fatal(doc: Mapping[str, Any]) -> None:
    gate = K.gate(doc, "source-probe-declared")
    assert gate["blocking"] is True
    assert gate["on_fail"] == "fail", (
        "the measured hole was a gate that returned ok on this input"
    )
    for clause in (
        "source_probe_declared == true",
        "source_probe_nonempty == true",
        "source_probe_is_an_invocation == true",
    ):
        assert clause in gate["expression"], (
            f"the source gate does not assert {clause!r}"
        )
    K.assert_precedes(K.top_level_stage_ids(doc), "source-gate", "select-verifier")


def check_independence_names_its_dimension_and_excludes_a_rerun(
    doc: Mapping[str, Any],
) -> None:
    gate = K.gate(doc, "verifier-is-independent")
    assert "verifier_fingerprint != source_fingerprint" in gate["expression"]
    assert "verifier_is_source_rerun == false" in gate["expression"]
    assert "independence_dimension_named == true" in gate["expression"], (
        "independence must be stated as a dimension, not inferred from a string difference"
    )
    assert gate["blocking"] is True and gate["on_fail"] == "fail"


def check_the_verifier_is_chosen_cross_vendor(doc: Mapping[str, Any]) -> None:
    selector = doc["roles"]["verifier-selector"]
    recorder = doc["roles"]["claim-recorder"]
    assert selector["vendor"] != recorder["vendor"]
    assert selector.get("cross_vendor_required") is True


def check_disagreement_does_not_authorise_the_action(doc: Mapping[str, Any]) -> None:
    gate = K.gate(doc, "action-authorised")
    assert "signals_agreed == true" in gate["expression"]
    assert "both_probes_recorded == true" in gate["expression"]
    assert gate["blocking"] is True
    assert gate["on_fail"] == "escalate-to-human"
    agree = K.gate(doc, "signals-agree")
    assert agree["on_fail"] == "repair", "a disagreement is investigated, not acted on"


def check_the_source_probe_itself_gets_a_both_states_control(
    doc: Mapping[str, Any],
) -> None:
    child = K.stage(doc, "validate-the-source-probe")
    assert child["kind"] == "subworkflow"
    assert child["workflow"]["workflow_id"] == "both-states-detector-control"
    assert child.get("when") == "signals_agreed == false"
    assert "both-states-detector-control" in doc["subworkflows"]
    declared = doc["subworkflows"]["both-states-detector-control"]["source"]
    assert (K.REPO_ROOT / declared).is_file(), (
        f"the declared child source is absent: {declared}"
    )


def check_the_checkpoint_fails_on_timeout(doc: Mapping[str, Any]) -> None:
    checkpoint = K.stage(doc, "authorise-action")
    assert checkpoint["kind"] == "human_checkpoint"
    assert checkpoint["on_timeout"] == "fail", (
        "a destructive action must never become authorised by nobody answering"
    )
    assert checkpoint["approval_mode"] == "owner-only"
    assert "abandon-the-action" in checkpoint["options"]


def check_destructive_tools_are_denied_to_the_gate_itself(
    doc: Mapping[str, Any],
) -> None:
    denied = set(doc["tool_policy"]["deny"])
    assert {"Bash:rm", "Bash:kill", "Bash:git-reset"} <= denied, (
        "the gate must not be able to perform the action it is deciding about"
    )
    assert doc["tool_policy"]["default"] == "deny"


def check_worst_case_reversibility_default(doc: Mapping[str, Any]) -> None:
    spec = doc["params"]["action_reversibility"]
    assert spec["type"] == "enum"
    assert spec["default"] == "hard", (
        "an undeclared reversibility defaults to worst-case (adverse inference), not to 'probably fine'"
    )


ALL_CHECKS = (
    check_source_probe_is_a_required_nonempty_param,
    check_the_source_gate_is_blocking_and_fatal,
    check_independence_names_its_dimension_and_excludes_a_rerun,
    check_the_verifier_is_chosen_cross_vendor,
    check_disagreement_does_not_authorise_the_action,
    check_the_source_probe_itself_gets_a_both_states_control,
    check_the_checkpoint_fails_on_timeout,
    check_destructive_tools_are_denied_to_the_gate_itself,
    check_worst_case_reversibility_default,
)


@pytest.mark.parametrize("check", ALL_CHECKS, ids=lambda c: c.__name__)
def test_shipped_blueprint_satisfies_every_mechanism_check(check: Any) -> None:
    check(DOC)


def test_shipped_blueprint_is_conformant() -> None:
    assert K.schema_errors(DOC) == []
    assert K.semantic_violations(DOC) == []


# ------------------------------------------------------------------------- mutation controls


def _make_source_probe_optional(doc: dict) -> None:
    doc["params"]["source_probe"].pop("required")


def _let_the_source_gate_record_and_continue(doc: dict) -> None:
    doc["gates"]["source-probe-declared"]["on_fail"] = "record-and-continue"
    doc["gates"]["source-probe-declared"]["blocking"] = False


def _accept_a_rerun_as_independent(doc: dict) -> None:
    doc["gates"]["verifier-is-independent"]["expression"] = (
        "verifier_fingerprint != source_fingerprint"
    )


def _make_the_selector_same_vendor(doc: dict) -> None:
    doc["roles"]["verifier-selector"]["vendor"] = doc["roles"]["claim-recorder"][
        "vendor"
    ]


def _authorise_on_disagreement(doc: dict) -> None:
    doc["gates"]["action-authorised"]["expression"] = "both_probes_recorded == true"


def _drop_the_child_control(doc: dict) -> None:
    doc["stages"] = [s for s in doc["stages"] if s["id"] != "validate-the-source-probe"]
    K.find_stage_mut(doc, "compare-readings")["depends_on"] = ["agreement-gate"]


def _let_the_checkpoint_proceed_on_timeout(doc: dict) -> None:
    K.find_stage_mut(doc, "authorise-action")["on_timeout"] = "proceed"


def _grant_destructive_tools(doc: dict) -> None:
    doc["tool_policy"]["deny"] = ["WebFetch"]


def _default_reversibility_to_trivial(doc: dict) -> None:
    doc["params"]["action_reversibility"]["default"] = "trivial"


MUTATIONS = (
    (check_source_probe_is_a_required_nonempty_param, _make_source_probe_optional),
    (
        check_the_source_gate_is_blocking_and_fatal,
        _let_the_source_gate_record_and_continue,
    ),
    (
        check_independence_names_its_dimension_and_excludes_a_rerun,
        _accept_a_rerun_as_independent,
    ),
    (check_the_verifier_is_chosen_cross_vendor, _make_the_selector_same_vendor),
    (check_disagreement_does_not_authorise_the_action, _authorise_on_disagreement),
    (check_the_source_probe_itself_gets_a_both_states_control, _drop_the_child_control),
    (check_the_checkpoint_fails_on_timeout, _let_the_checkpoint_proceed_on_timeout),
    (check_destructive_tools_are_denied_to_the_gate_itself, _grant_destructive_tools),
    (check_worst_case_reversibility_default, _default_reversibility_to_trivial),
)


@pytest.mark.parametrize(
    "check,mutate", MUTATIONS, ids=lambda v: getattr(v, "__name__", "")
)
def test_each_check_fails_on_its_mutated_blueprint(check: Any, mutate: Any) -> None:
    broken = K.mutant(DOC, mutate)
    assert K.raises_assertion(check, broken), (
        f"{check.__name__} stayed silent on the mutated blueprint, so it measures nothing"
    )


def test_the_optional_source_probe_mutant_is_schema_legal() -> None:
    """This is the measured hole in its exact shape: valid DSL, and only this test rejects it."""
    broken = K.mutant(DOC, _make_source_probe_optional)
    assert K.schema_errors(broken) == []
    assert K.semantic_violations(broken) == []
    assert K.raises_assertion(check_source_probe_is_a_required_nonempty_param, broken)


def test_the_proceed_on_timeout_mutant_is_schema_legal() -> None:
    broken = K.mutant(DOC, _let_the_checkpoint_proceed_on_timeout)
    assert K.schema_errors(broken) == []
    assert K.raises_assertion(check_the_checkpoint_fails_on_timeout, broken)
