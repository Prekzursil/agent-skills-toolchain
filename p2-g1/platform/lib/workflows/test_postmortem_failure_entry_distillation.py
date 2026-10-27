"""End-to-end tests for BP-INC-04 (card 70), postmortem to failure-entry distillation.

Mechanism under test: a SCRIPT-FIRST redirect (a rule a deterministic check could enforce is
refused as a rule) plus a BIDIRECTIONAL temporal supersede link (the new note carries valid_as_of
and the old note is stamped superseded_by). The arbiter that performs the redirect is cross-vendor
from the distiller that proposed the rule.
"""

from __future__ import annotations

import pytest

import _harness as H

NAME = "postmortem-failure-entry-distillation"


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


def test_worked_example_checker_fires_on_an_undeclared_param(doc: dict) -> None:
    def bend(d: dict) -> None:
        d["x_extensions"]["worked_example"]["params"]["invented_param"] = True

    fails = H.worked_example_failures(H.mutated(doc, bend))
    assert any("undeclared param" in f for f in fails), fails


def test_it_is_declared_a_meta_workflow(doc: dict) -> None:
    assert doc["kind"] == "meta-workflow"
    assert "collective-intelligence-and-meta" in doc["categories"]


# ------------------------------------------------ mechanism: falsifiable preconditions or nothing


def test_preconditions_must_carry_a_testable_observation(doc: dict) -> None:
    expr = H.gate_expressions(doc)["preconditions-are-falsifiable"]
    assert "preconditions_stated >= 1" in expr
    assert "preconditions_without_a_testable_observation == 0" in expr
    unit = H.stage(doc, "state-failure-with-preconditions")["work_unit"]
    assert "would make it recur" in unit["question_or_target"]
    assert "precondition-untestable" in unit["failure_classification"]


def test_an_unknown_root_cause_is_recorded_rather_than_guessed(doc: dict) -> None:
    spec = doc["params"]["root_cause"]
    assert spec.get("required") is not True, (
        "an unknown root cause must be a legal state"
    )
    unit = H.stage(doc, "state-failure-with-preconditions")["work_unit"]
    assert (
        "mark the entry unresolved rather than guessing" in unit["question_or_target"]
    )
    tests = " ".join(unit["tests_required"])
    assert "root_cause unset must still be accepted" in tests
    rules = {r["id"]: r for r in doc["stopping_rules"]}
    unknown = rules["root-cause-unknown-record-symptom"]
    assert unknown["expression"] == "root_cause_known == false"
    assert unknown["minimum_conditions"] == "ruled_out_count >= 1"
    assert unknown["on_stop"] == "emit-partial"


# ------------------------------------------------------ mechanism: script-first redirect


def test_the_script_first_gate_forbids_a_mechanisable_rule(doc: dict) -> None:
    assert H.gate_expressions(doc)["script-first"] == (
        "rule_proposals_a_script_could_enforce == 0"
    )
    assert doc["gates"]["script-first"]["on_fail"] == "repair"
    order = H.top_level_stage_ids(doc)
    assert order.index("rule-or-script") < order.index("script-first-gate")
    assert order.index("script-first-gate") < order.index("write-ledger-and-memory")


def test_the_arbiter_is_cross_vendor_from_the_rule_author_and_holds_veto(
    doc: dict,
) -> None:
    distiller = doc["roles"]["distiller"]
    arbiter = doc["roles"]["script-first-arbiter"]
    assert arbiter["vendor"] != distiller["vendor"]
    assert arbiter["cross_vendor_required"] is True
    assert arbiter["authority"] == "veto"
    unit = H.stage(doc, "rule-or-script")["work_unit"]
    assert unit["assigned_model_vendor_role"]["role"] == "script-first-arbiter"
    assert "holds veto authority on the redirect" in unit["reviewer_requirement"]


def test_a_redirect_must_sketch_the_check_and_the_arbiter_must_not_redirect_everything(
    doc: dict,
) -> None:
    unit = H.stage(doc, "rule-or-script")["work_unit"]
    ev = unit["evidence_requirement"]
    assert "input, comparison, exit condition" in ev
    assert "no sketched check is not a redirect" in ev
    tests = " ".join(unit["tests_required"])
    assert "must be redirected to SCRIPT" in tests
    assert "must survive as RULE" in tests, (
        "an arbiter that redirects everything is as broken as one that redirects nothing"
    )
    assert "redirect-without-check" in unit["failure_classification"]
    assert "rule-accretion" in doc["retry_policy"]["no_retry_on"]


def test_removing_the_script_first_gate_is_detected(doc: dict) -> None:
    def bend(d: dict) -> None:
        del d["gates"]["script-first"]

    violations = H.semantic_violations(H.mutated(doc, bend))
    assert any("DSL-SEM-005" in v and "script-first" in v for v in violations), (
        violations
    )


# ------------------------------------------- mechanism: the supersede link goes BOTH directions


def test_a_contradiction_without_a_supersede_edge_fails(doc: dict) -> None:
    assert H.gate_expressions(doc)["supersede-edge-present-when-contradicting"] == (
        "contradicted_entries_without_supersede_edge == 0"
    )
    unit = H.stage(doc, "find-contradicted-entries")["work_unit"]
    assert "never deleted" in unit["question_or_target"]
    assert "re-walked" in unit["question_or_target"]
    ev = unit["evidence_requirement"]
    assert "refuting measurement" in ev, (
        "a supersede with no refuting measurement is an opinion"
    )
    tests = " ".join(unit["tests_required"])
    assert "explicit empty edge set, not silence" in tests


def test_temporal_validity_is_asserted_in_both_directions(doc: dict) -> None:
    expr = H.gate_expressions(doc)["memory-note-carries-temporal-validity"]
    assert "notes_without_valid_as_of == 0" in expr
    assert "superseded_notes_without_superseded_by == 0" in expr
    unit = H.stage(doc, "write-ledger-and-memory")["work_unit"]
    tests = " ".join(unit["tests_required"])
    assert "both directions of the temporal link" in tests
    assert "supersede-one-directional" in unit["failure_classification"]
    assert "supersede-one-directional" in doc["retry_policy"]["no_retry_on"]
    assert "fresh-context reader" in unit["reviewer_requirement"]


def test_dropping_the_superseded_by_half_is_detectable(doc: dict) -> None:
    def bend(d: dict) -> None:
        d["gates"]["memory-note-carries-temporal-validity"]["expression"] = (
            "notes_without_valid_as_of == 0"
        )

    mutant = H.mutated(doc, bend)
    assert H.conformance_failures(mutant) == []
    assert (
        "superseded_by"
        not in H.gate_expressions(mutant)["memory-note-carries-temporal-validity"]
    )


def test_the_durable_writes_are_the_declared_outputs(doc: dict) -> None:
    paths = H.declared_paths(doc)
    for expected in (
        "command-center/knowledge/failure-entry.json",
        "command-center/knowledge/supersede-edges.json",
        "command-center/knowledge/rule-or-script.json",
        "command-center/knowledge/postmortem-receipt.json",
    ):
        assert expected in paths, expected
    assert "mcp__basic-memory__write_note" in doc["tool_policy"]["allow"]
    assert "mcp__basic-memory__write_note" in doc["dry_run"]["forbid_tools"], (
        "a dry run must not write a durable memory note"
    )


def test_a_promised_migration_must_be_declared(doc: dict) -> None:
    imp = doc["portability"]["import"]
    assert imp["on_version_mismatch"] == "migrate"
    assert imp["migrations"], (
        "promising to migrate without a migration is an empty promise"
    )

    def bend(d: dict) -> None:
        del d["portability"]["import"]["migrations"]

    errs = H.schema_errors(H.mutated(doc, bend))
    assert any("migrations" in e for e in errs), errs
