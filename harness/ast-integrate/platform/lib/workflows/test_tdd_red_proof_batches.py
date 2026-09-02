"""FLAGSHIP end-to-end test for `tdd-red-proof-batches` (bp-4, doc-order 41, BP-IMP-04).

Mechanism claims under test: the RED capture is a STORED receipt of the runner's real output at a
recorded pre-fix sha; nothing may be implemented before that gate; a test that was already green
pre-fix is reclassified rather than silently fixed; the capture step is explicitly NO-RETRY so a
second attempt cannot manufacture a red; and the green capture must not have been reached by
deleting assertions.
"""

from __future__ import annotations

from typing import Any, Mapping

import bp4_testkit as K
import pytest

WORKFLOW_ID = "tdd-red-proof-batches"
DOC = K.load(WORKFLOW_ID)

BATCH_BODY_ORDER = (
    "write-failing-test",
    "red-gate",
    "implement-fix",
    "capture-green",
    "green-gate",
    "mutation-check",
    "mutation-gate",
    "review-both-proofs",
    "commit-batch",
)


def _body_ids(doc: Mapping[str, Any]) -> list[str]:
    return [st["id"] for st in K.stage(doc, "batch-pipelines")["body"]]


# ------------------------------------------------------------------------------- the checks


def check_red_gate_precedes_implementation(doc: Mapping[str, Any]) -> None:
    ids = _body_ids(doc)
    assert ids == list(BATCH_BODY_ORDER), f"batch body order changed: {ids}"
    body = {st["id"]: st for st in K.stage(doc, "batch-pipelines")["body"]}
    assert body["red-gate"]["depends_on"] == ["write-failing-test"]
    assert body["implement-fix"]["depends_on"] == ["red-gate"], (
        "implementation must be downstream of the red gate, not merely later in the list"
    )


def check_red_proof_is_a_stored_receipt(doc: Mapping[str, Any]) -> None:
    capture = K.stage(doc, "write-failing-test")
    produced = {a["path"]: a for a in capture["produces"]}
    receipt = produced.get("command-center/redproof/red-receipt.json")
    assert receipt is not None, "the red proof must be an artifact, not an assertion"
    assert receipt["schema_ref"].endswith("failing-test-receipt.schema.json")
    assert receipt["min_bytes"] >= 128
    assert K.resolve_schema_reference(receipt["schema_ref"]) is not None
    unit = capture["work_unit"]
    assert unit["output_schema"].endswith("failing-test-receipt.schema.json")
    assert "verbatim" in unit["evidence_requirement"]
    assert "pre-fix" in unit["evidence_requirement"]


def check_green_before_fix_is_rejected(doc: Mapping[str, Any]) -> None:
    gate = K.gate(doc, "red-proof-captured")
    assert gate["blocking"] is True
    for clause in (
        "red_capture_present == true",
        "red_capture_is_runner_output == true",
        "test_was_green_before_fix == false",
    ):
        assert clause in gate["expression"], f"the red gate does not assert {clause!r}"
    assert gate["on_fail"] == "escalate-to-human", (
        "a defect with no obtainable red proof is reclassified by a human, not retried"
    )


def check_capture_step_is_no_retry(doc: Mapping[str, Any]) -> None:
    retry = K.stage(doc, "write-failing-test").get("retry")
    assert retry is not None, "the capture step must pin its own retry policy"
    assert retry["strategy"] == "none" and retry["max_attempts"] == 1, (
        "a second attempt to make a passing test fail is how a fake red proof gets written"
    )
    assert "green-before-fix" in doc["retry_policy"]["no_retry_on"]


def check_green_capture_cannot_be_reached_by_weakening_the_test(
    doc: Mapping[str, Any],
) -> None:
    gate = K.gate(doc, "green-proof-captured")
    assert "test_body_unchanged_since_red == true" in gate["expression"]
    assert "assertions_removed == 0" in gate["expression"]
    assert gate["blocking"] is True and gate["on_fail"] == "fail"


def check_mutation_stage_is_optional_but_records_survivors(
    doc: Mapping[str, Any],
) -> None:
    stage = K.stage(doc, "mutation-check")
    assert stage.get("when") == "mutation_check == true"
    gate = K.gate(doc, "mutation-noticed")
    assert gate["blocking"] is False, "a surviving mutant is a flag, not a hard stop"
    assert gate["on_fail"] == "record-and-continue"
    assert "surviving_mutants == 0" in gate["expression"]
    assert "mutation-survived" in doc["failure_policy"]["classify_as"]


def check_batches_are_file_disjoint(doc: Mapping[str, Any]) -> None:
    gate = K.gate(doc, "batches-file-disjoint")
    assert "overlapping_files_between_batches == 0" in gate["expression"]
    K.assert_precedes(
        K.top_level_stage_ids(doc), "disjointness-gate", "batch-pipelines"
    )


def check_run_wide_audit_requires_a_proof_per_fixed_defect(
    doc: Mapping[str, Any],
) -> None:
    audit = K.stage(doc, "red-proof-audit")
    assert audit["kind"] == "gate"
    expression = audit["gate"]["expression"]
    assert "fixed_defects_without_red_proof == 0" in expression
    assert "reclassified_defects_recorded == true" in expression
    assert audit["gate"]["blocking"] is True


def check_reclassification_is_a_human_decision_with_an_artifact(
    doc: Mapping[str, Any],
) -> None:
    checkpoint = K.stage(doc, "reclassify-untestable")
    assert checkpoint["kind"] == "human_checkpoint"
    assert checkpoint["approval_mode"] == "owner-only"
    assert checkpoint["decision_artifact"]["path"].endswith("reclassification.json")
    assert set(checkpoint["options"]) == {
        "not-reproducible",
        "test-was-wrong",
        "untestable-and-disclosed",
    }


ALL_CHECKS = (
    check_red_gate_precedes_implementation,
    check_red_proof_is_a_stored_receipt,
    check_green_before_fix_is_rejected,
    check_capture_step_is_no_retry,
    check_green_capture_cannot_be_reached_by_weakening_the_test,
    check_mutation_stage_is_optional_but_records_survivors,
    check_batches_are_file_disjoint,
    check_run_wide_audit_requires_a_proof_per_fixed_defect,
    check_reclassification_is_a_human_decision_with_an_artifact,
)


@pytest.mark.parametrize("check", ALL_CHECKS, ids=lambda c: c.__name__)
def test_shipped_blueprint_satisfies_every_mechanism_check(check: Any) -> None:
    check(DOC)


def test_shipped_blueprint_is_conformant() -> None:
    assert K.schema_errors(DOC) == []
    assert K.semantic_violations(DOC) == []


# ------------------------------------------------------------------------- mutation controls


def _implement_before_the_red_gate(doc: dict) -> None:
    K.find_stage_mut(doc, "implement-fix")["depends_on"] = ["write-failing-test"]


def _turn_the_receipt_into_an_assertion(doc: dict) -> None:
    K.find_stage_mut(doc, "write-failing-test")["produces"] = [
        {
            "path": "command-center/redproof/note.json",
            "schema_ref": "command-center/schema/test-receipt.schema.json",
            "min_bytes": 128,
        }
    ]


def _drop_the_green_before_fix_clause(doc: dict) -> None:
    doc["gates"]["red-proof-captured"]["expression"] = "red_capture_present == true"


def _allow_retrying_the_capture(doc: dict) -> None:
    K.find_stage_mut(doc, "write-failing-test")["retry"] = {
        "strategy": "fixed",
        "max_attempts": 3,
        "backoff_seconds": 5,
    }


def _permit_assertion_removal(doc: dict) -> None:
    doc["gates"]["green-proof-captured"]["expression"] = "green_capture_present == true"


def _make_mutation_gate_blocking_and_lose_the_record(doc: dict) -> None:
    doc["gates"]["mutation-noticed"]["blocking"] = True
    doc["gates"]["mutation-noticed"]["on_fail"] = "fail"


def _run_batches_without_the_disjointness_gate(doc: dict) -> None:
    doc["stages"] = [s for s in doc["stages"] if s["id"] != "disjointness-gate"]
    K.find_stage_mut(doc, "batch-pipelines")["depends_on"] = ["group-batches"]


def _weaken_the_run_wide_audit(doc: dict) -> None:
    K.find_stage_mut(doc, "red-proof-audit")["gate"]["expression"] = (
        "run_completed == true"
    )


def _let_anyone_reclassify(doc: dict) -> None:
    K.find_stage_mut(doc, "reclassify-untestable")["approval_mode"] = "any"


MUTATIONS = (
    (check_red_gate_precedes_implementation, _implement_before_the_red_gate),
    (check_red_proof_is_a_stored_receipt, _turn_the_receipt_into_an_assertion),
    (check_green_before_fix_is_rejected, _drop_the_green_before_fix_clause),
    (check_capture_step_is_no_retry, _allow_retrying_the_capture),
    (
        check_green_capture_cannot_be_reached_by_weakening_the_test,
        _permit_assertion_removal,
    ),
    (
        check_mutation_stage_is_optional_but_records_survivors,
        _make_mutation_gate_blocking_and_lose_the_record,
    ),
    (check_batches_are_file_disjoint, _run_batches_without_the_disjointness_gate),
    (
        check_run_wide_audit_requires_a_proof_per_fixed_defect,
        _weaken_the_run_wide_audit,
    ),
    (
        check_reclassification_is_a_human_decision_with_an_artifact,
        _let_anyone_reclassify,
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


def test_dropping_the_green_before_fix_clause_is_schema_legal() -> None:
    """The anti-faking clause is not enforceable by schema - only this test protects it."""
    broken = K.mutant(DOC, _drop_the_green_before_fix_clause)
    assert K.schema_errors(broken) == []
    assert K.semantic_violations(broken) == []
    assert K.raises_assertion(check_green_before_fix_is_rejected, broken)
