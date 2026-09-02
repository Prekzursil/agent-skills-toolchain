"""End-to-end tests for BP-INC-01 (card 67), live-estate incident triage.

Mechanism under test: the ACTION is gated, not the diagnosis. Each claim is probed by two
instruments from DIFFERENT declared classes, the pair is chosen before either runs, an
environmental explanation is tested before any defect is concluded, and only a corroborated claim
can release a restart / kill / rollback.
"""

from __future__ import annotations

import pytest

import _harness as H

NAME = "live-estate-incident-triage"


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


def test_worked_example_declares_why_the_owner_stage_is_skipped(doc: dict) -> None:
    ex = doc["x_extensions"]["worked_example"]
    assert ex["skipped_stages"] == ["owner-authorises-disruptive-action"]
    assert "allow_disruptive_actions is false" in ex["skipped_because"]

    def bend(d: dict) -> None:
        del d["x_extensions"]["worked_example"]["skipped_because"]

    fails = H.worked_example_failures(H.mutated(doc, bend))
    assert any("without skipped_because" in f for f in fails), fails


# ------------------------------------------------- mechanism: two DIFFERENT instrument classes


def test_at_least_two_instrument_classes_are_required_by_the_param_contract(
    doc: dict,
) -> None:
    spec = doc["params"]["instrument_classes"]
    assert spec["min_items"] >= 2, "one instrument class cannot corroborate itself"
    assert spec["items"]["type"] == "enum"
    classes = spec["items"]["enum"]
    # the declared classes must be mechanically different families, not synonyms of one source
    assert {"process-table", "file-mtime", "event-log", "exit-code-decode"} <= set(
        classes
    )
    assert len(set(classes)) == len(classes), (
        "a duplicated class inflates the apparent count"
    )


def test_the_instrument_pair_is_chosen_before_either_probe_runs(doc: dict) -> None:
    claims = H.stage(doc, "state-claims")["work_unit"]
    assert "named before either is run" in claims["evidence_requirement"]
    tests = " ".join(claims["tests_required"])
    assert "identical must be rejected before any probe runs" in tests
    assert "instrument-pair-degenerate" in claims["failure_classification"]


def test_the_independence_gate_rejects_a_same_probe_rerun(doc: dict) -> None:
    expr = H.gate_expressions(doc)["instruments-are-independent"]
    assert "distinct_instrument_classes_used >= 2" in expr
    assert "same_probe_rerun_count == 0" in expr, (
        "re-running the producing probe is the measured way a false corroboration is manufactured"
    )
    body = [s["id"] for s in H.stage(doc, "probe-claims")["body"]]
    assert body == ["probe-primary", "probe-corroborating", "independence-gate"]
    assert H.stage(doc, "independence-gate")["depends_on"] == [
        "probe-primary",
        "probe-corroborating",
    ]


def test_the_source_probe_is_declared_not_only_the_verifier(doc: dict) -> None:
    """An undeclared source probe is zero signals, not one - so the primary probe records itself."""
    primary = H.stage(doc, "probe-primary")["work_unit"]
    assert "SOURCE probe must be declared" in primary["question_or_target"]
    assert "instrument class token" in primary["evidence_requirement"]
    assert "probe-self-match" in primary["failure_classification"]
    tests = " ".join(primary["tests_required"])
    assert "matches its OWN command line" in tests, (
        "the self-match control must be present"
    )


def test_dropping_the_independence_gate_leaves_a_dangling_reference(doc: dict) -> None:
    def bend(d: dict) -> None:
        del d["gates"]["instruments-are-independent"]

    violations = H.semantic_violations(H.mutated(doc, bend))
    assert any(
        "DSL-SEM-005" in v and "instruments-are-independent" in v for v in violations
    ), violations


# --------------------------------------------- mechanism: environmental check before defect


def test_an_environmental_explanation_is_tested_before_a_defect_is_declared(
    doc: dict,
) -> None:
    order = H.top_level_stage_ids(doc)
    assert order.index("environmental-explanation") < order.index("action-gate")
    unit = H.stage(doc, "environmental-explanation")["work_unit"]
    assert "power-off" in unit["question_or_target"]
    ev = unit["evidence_requirement"]
    assert "compared numerically" in ev and "both numbers" in ev
    tests = " ".join(unit["tests_required"])
    assert "power-off window must reclassify to ENVIRONMENTAL" in tests
    assert "log-rollover control" in tests, (
        "an absence of log events across a gap needs a rollover control before it reads as a gap"
    )


def test_a_single_signal_verdict_is_impossible_by_construction(doc: dict) -> None:
    expr = H.gate_expressions(doc)["every-claim-has-a-verdict"]
    assert "claims_with_verdict == claims_stated" in expr
    assert "claims_with_single_signal == 0" in expr
    recon = H.stage(doc, "reconcile-readings")["work_unit"]
    assert "single-signal-verdict" in recon["failure_classification"]
    assert "single-signal-verdict" in doc["retry_policy"]["no_retry_on"]
    tests = " ".join(recon["tests_required"])
    assert "only one reading must be UNRESOLVED" in tests


# ---------------------------------------------------- mechanism: the ACTION is what is gated


def test_disruptive_actions_require_corroboration_and_an_owner_signature(
    doc: dict,
) -> None:
    expr = H.gate_expressions(doc)["action-authorised-only-on-corroboration"]
    assert "disruptive_actions_proposed_without_corroborated_claim == 0" in expr
    assert "environmental_explanation_checked == true" in expr
    cp = H.stage(doc, "owner-authorises-disruptive-action")
    assert cp["kind"] == "human_checkpoint"
    assert (
        cp["when"]
        == "allow_disruptive_actions == true AND disruptive_actions_proposed >= 1"
    )
    assert cp["on_timeout"] == "fail"
    assert doc["params"]["allow_disruptive_actions"]["default"] is False


def test_the_workflow_holds_no_tool_that_could_kill_or_roll_back_unilaterally(
    doc: dict,
) -> None:
    tokens = H.all_tool_tokens(doc)
    for banned in ("Bash", "Bash:taskkill", "Bash:git"):
        assert banned in doc["tool_policy"]["deny"], banned
        assert banned not in tokens, banned
    assert "Bash:pwsh" in doc["tool_policy"]["require_owner_approval"]


def test_an_unresolved_claim_emits_a_partial_rather_than_completing(doc: dict) -> None:
    rules = {r["id"]: r for r in doc["stopping_rules"]}
    unresolved = rules["second-signal-unobtainable"]
    assert unresolved["expression"] == "claims_unresolved >= 1"
    assert unresolved["on_stop"] == "emit-partial"
    assert rules["every-claim-decided-and-actions-listed"]["minimum_conditions"] == (
        "distinct_instrument_classes_used >= 2"
    )
