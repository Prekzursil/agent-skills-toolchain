"""End-to-end tests for BP-SEC-04 (card 64), the fail-closed supply-chain campaign.

Mechanism under test: a SECOND-ORDER audit of the gate. The per-repo runners record raw CI facts;
a separate cross-vendor auditor converts them into PASS / FAIL / UNGATED and is the only role
permitted to overturn a repo's self-reported pass. Three fail-open readings are inverted, and the
campaign's headline output is the UNGATED list rather than the PASS count.
"""

from __future__ import annotations

import pytest

import _harness as H

NAME = "supply-chain-alert-campaign-fail-closed"


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


def test_worked_example_checker_fires_on_an_out_of_pattern_value(doc: dict) -> None:
    def bend(d: dict) -> None:
        d["x_extensions"]["worked_example"]["params"]["snapshot_date"] = "yesterday"

    fails = H.worked_example_failures(H.mutated(doc, bend))
    assert any("does not match its declared pattern" in f for f in fails), fails


# ---------------------------------------------- mechanism: the audit is a separate, later role


def test_the_gate_audit_is_a_distinct_cross_vendor_role_with_veto(doc: dict) -> None:
    runner = doc["roles"]["repo-runner"]
    auditor = doc["roles"]["gate-auditor"]
    assert auditor["vendor"] != runner["vendor"], (
        "an auditor sharing the runner's vendor inherits its reading of its own output"
    )
    assert auditor["cross_vendor_required"] is True
    assert auditor["authority"] == "veto"
    assert auditor["independence"] == "cross-examining"
    order = H.top_level_stage_ids(doc)
    assert order.index("run-per-repo") < order.index("audit-the-gate")
    assert H.stage(doc, "audit-the-gate")["depends_on"] == ["run-per-repo"]


def test_only_the_auditor_may_produce_a_verdict(doc: dict) -> None:
    raw = H.stage(doc, "read-real-ci-result")["work_unit"]
    assert "checks:NONE, not PASS" in " ".join(raw["tests_required"])
    assert "only role permitted to convert" in raw["reviewer_requirement"]
    audited = H.stage(doc, "audit-the-gate")["work_unit"]
    assert audited["assigned_model_vendor_role"]["role"] == "gate-auditor"


# ------------------------------------------------ mechanism: three fail-open inversions


def test_the_three_inversions_are_named_in_the_audit_unit(doc: dict) -> None:
    target = H.stage(doc, "audit-the-gate")["work_unit"]["question_or_target"]
    assert "UNGATED regardless of any CLEAN summary" in target
    assert "BLOCKED with a failed run is FAIL not pending" in target
    assert "tool auth failure while reading CI is UNGATED not PASS" in target


def test_the_fail_closed_gate_requires_zero_ungated_and_zero_missing(doc: dict) -> None:
    expr = H.gate_expressions(doc)["no-repo-ungated"]
    assert "repos_ungated == 0" in expr
    assert "repos_without_verdict == 0" in expr, (
        "a repo with no verdict at all is the quietest fail-open of the three"
    )
    assert doc["gates"]["no-repo-ungated"]["on_fail"] == "escalate-to-human"


def test_the_detector_can_also_say_PASS(doc: dict) -> None:
    """A gate audit that always answers UNGATED would be useless; the unit tests both directions."""
    tests = " ".join(H.stage(doc, "audit-the-gate")["work_unit"]["tests_required"])
    assert "must audit to UNGATED" in tests
    assert "must audit to PASS" in tests
    assert "must not simply always say UNGATED" in tests


def test_weakening_the_gate_to_ignore_missing_verdicts_is_detectable(doc: dict) -> None:
    def bend(d: dict) -> None:
        d["gates"]["no-repo-ungated"]["expression"] = "repos_ungated == 0"

    mutant = H.mutated(doc, bend)
    assert H.conformance_failures(mutant) == []
    assert "repos_without_verdict" not in H.gate_expressions(mutant)["no-repo-ungated"]


# ------------------------------------------------ mechanism: a tool error is not zero findings


def test_a_non_finding_exit_code_is_classified_as_a_tool_error(doc: dict) -> None:
    collector = H.stage(doc, "collect-advisories")["work_unit"]
    assert "127" in collector["question_or_target"]
    assert "TOOL-ERROR" in collector["question_or_target"]
    assert "tool-error-read-as-zero" in collector["failure_classification"]
    assert "advisory_source_reachable == true" in H.gate_expressions(doc)["advisory-source-live"]
    assert "tool-error-read-as-zero" in doc["retry_policy"]["no_retry_on"]


def test_a_dead_advisory_source_halts_rather_than_reporting_zero(doc: dict) -> None:
    stop = {r["id"]: r for r in doc["stopping_rules"]}["halt-on-dead-advisory-source"]
    assert stop["expression"] == "advisory_source_reachable == false"
    assert stop["on_stop"] == "escalate"


# ------------------------------------------------- mechanism: two-directional fork sync check


def test_the_fork_check_is_two_directional(doc: dict) -> None:
    unit = H.stage(doc, "check-sync-direction")["work_unit"]
    assert "ahead_by and behind_by" in unit["evidence_requirement"]
    assert "a single number is not a direction" in unit["evidence_requirement"]
    assert "would-delete-local-fixes" in unit["failure_classification"]
    assert "would-delete-local-fixes" in doc["retry_policy"]["no_retry_on"]
    assert H.stage(doc, "check-sync-direction")["when"] == "repo_is_fork == true"


# --------------------------------------------------------- honesty: replay is NOT deterministic


def test_replay_is_declared_non_deterministic_because_advisories_move(doc: dict) -> None:
    assert doc["replay"]["deterministic"] is False
    assert doc["params"]["snapshot_date"]["required"] is True
    assert doc["cache"]["invalidate_on"] == ["snapshot-date-change"]
    assert doc["estimate"]["confidence"] == "roughly-even"


def test_claiming_determinism_without_a_seed_would_be_rejected(doc: dict) -> None:
    def bend(d: dict) -> None:
        d["replay"]["deterministic"] = True

    errs = H.schema_errors(H.mutated(doc, bend))
    assert any("seed" in e for e in errs), errs


def test_release_mode_is_propose_only(doc: dict) -> None:
    assert doc["params"]["propose_only"]["default"] is True
    assert doc["estimate"]["impact"]["requires_owner_approval"] is True
    assert "Bash:gh" in doc["tool_policy"]["require_owner_approval"]
    assert "never auto-merge" in H.stage(doc, "open-draft-bump")["title"].lower()
