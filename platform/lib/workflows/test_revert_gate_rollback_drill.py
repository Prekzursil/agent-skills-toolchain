"""End-to-end tests for BP-INC-05 (card 71), the revert-gate rollback drill.

Mechanism under test: reversibility is DEMONSTRATED before the change is applied for real. The
baseline is bytes (a digest per path plus a manifest digest, including negative existence so a
created file is detectable), the postcondition proves the change did something while applied, and
the revert must restore the manifest exactly with an explicitly empty residual list.
"""

from __future__ import annotations

import pytest

import _harness as H

NAME = "revert-gate-rollback-drill"


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


def test_worked_example_checker_fires_on_a_bad_terminal_sentinel(doc: dict) -> None:
    def bend(d: dict) -> None:
        d["x_extensions"]["worked_example"]["expected_terminal"] = "SUCCESS:XX-9999"

    fails = H.worked_example_failures(H.mutated(doc, bend))
    assert any("not an inline work unit here" in f for f in fails), fails


# --------------------------------------------------- mechanism: the baseline is bytes, with a negative


def test_the_baseline_records_a_digest_per_path_and_a_manifest_digest(doc: dict) -> None:
    unit = H.stage(doc, "capture-baseline")["work_unit"]
    target = unit["question_or_target"]
    assert "digest" in target and "manifest digest" in target
    ev = unit["evidence_requirement"]
    assert "existence flag" in ev, (
        "without a negative existence flag a file CREATED by the change has no baseline row"
    )
    tests = " ".join(unit["tests_required"])
    assert "existence false" in tests
    assert "sorted-rows control" in tests, "a walk-order-dependent digest is not a digest"
    assert "baseline-uncapturable" in unit["failure_classification"]


def test_an_uncapturable_baseline_is_never_retried_into_existence(doc: dict) -> None:
    assert doc["retry_policy"]["strategy"] == "none"
    assert doc["retry_policy"]["max_attempts"] == 1
    assert "baseline-uncapturable" in doc["retry_policy"]["no_retry_on"]
    assert "revert-left-residue" in doc["retry_policy"]["no_retry_on"]


# ----------------------------------- mechanism: the change must actually do something


def test_the_postcondition_gate_rejects_a_no_op_change(doc: dict) -> None:
    expr = H.gate_expressions(doc)["change-actually-did-something"]
    assert "postcondition_result == PASS" in expr
    assert "applied_manifest_differs_from_baseline == true" in expr, (
        "a change that changed nothing has a trivially perfect revert, which proves nothing"
    )
    assert doc["params"]["postcondition"]["required"] is True
    assert "trivially perfect revert" in H.stage(doc, "postcondition-gate")["title"]


def test_dropping_the_no_op_clause_weakens_the_gate_detectably(doc: dict) -> None:
    def bend(d: dict) -> None:
        d["gates"]["change-actually-did-something"]["expression"] = "postcondition_result == PASS"

    mutant = H.mutated(doc, bend)
    assert H.conformance_failures(mutant) == []
    assert "applied_manifest_differs_from_baseline" not in H.gate_expressions(mutant)[
        "change-actually-did-something"
    ]


# --------------------------------------------- mechanism: byte equality plus a residual list


def test_the_revert_gate_asserts_digest_equality_and_zero_residue(doc: dict) -> None:
    expr = H.gate_expressions(doc)["revert-restores-bytes-exactly"]
    assert "post_revert_manifest_digest == baseline_manifest_digest" in expr
    assert "residual_paths == 0" in expr
    unit = H.stage(doc, "compare-to-baseline")["work_unit"]
    ev = unit["evidence_requirement"]
    assert "explicit residual-path list" in ev
    assert "created, modified or deleted" in ev
    assert "empty list is stated as empty rather than omitted" in ev
    tests = " ".join(unit["tests_required"])
    assert "one stray file" in tests, "the residue control must exist"
    assert "not a 'looks the same' verdict" in tests


def test_the_drill_order_is_baseline_apply_check_revert_compare(doc: dict) -> None:
    body = [s["id"] for s in H.stage(doc, "drill-each-change")["body"]]
    assert body == [
        "capture-baseline",
        "apply-in-drill",
        "postcondition-gate",
        "revert-in-drill",
        "compare-to-baseline",
        "residue-gate",
    ], body
    # each step waits on the one before: a comparison that can run before the revert is useless
    assert H.stage(doc, "compare-to-baseline")["depends_on"] == ["revert-in-drill"]
    assert H.stage(doc, "residue-gate")["depends_on"] == ["compare-to-baseline"]


def test_reordering_the_drill_so_the_comparison_precedes_the_revert_is_caught(doc: dict) -> None:
    """A comparison that no longer waits on the revert is a real defect; DSL-SEM-003 catches the
    cycle produced by making the revert wait on the comparison instead."""

    def bend(d: dict) -> None:
        for s in d["stages"][0]["body"]:
            if s["id"] == "revert-in-drill":
                s["depends_on"] = ["compare-to-baseline"]

    violations = H.semantic_violations(H.mutated(doc, bend))
    assert any("DSL-SEM-003" in v for v in violations), violations


# ------------------------------------------------------- mechanism: drills are serialized


def test_drills_are_strictly_serialized_and_abort_on_the_first_failure(doc: dict) -> None:
    fan = H.stage(doc, "drill-each-change")
    assert fan["max_concurrency"] == 1, (
        "two drills against one tree would each be the other's residue"
    )
    assert fan["on_item_failure"] == "abort"
    assert fan["barrier"]["mode"] == "all"
    assert fan["barrier"]["on_partial"] == "fail"
    assert doc["resume"]["resume_from"] == "restart", (
        "resuming a half-applied drill from a checkpoint would leave the tree in the applied state"
    )


# ------------------------------------------- mechanism: undrillable escalates, never applies


def test_an_undrillable_change_reaches_the_owner_and_is_not_applied(doc: dict) -> None:
    cp = H.stage(doc, "owner-decides-undrillable")
    assert cp["kind"] == "human_checkpoint"
    assert cp["when"] == "undrillable_changes >= 1"
    assert cp["on_timeout"] == "fail"
    assert "accept-irreversibility-explicitly" in cp["options"]
    assert "will not be applied on the strength of this workflow" in cp["prompt"]
    expr = H.gate_expressions(doc)["real-apply-authorised"]
    assert "drills_passed == drills_attempted" in expr
    assert "undrillable_changes_applied == 0" in expr
    rules = {r["id"]: r for r in doc["stopping_rules"]}
    assert rules["revert-unprovable"]["on_stop"] == "escalate"


def test_the_estimate_admits_the_drill_really_touches_the_target(doc: dict) -> None:
    impact = doc["estimate"]["impact"]
    assert impact["risk"] == "medium"
    assert "APPLIES the change temporarily" in impact["blast_radius"]
    assert "doubling the apply cost is the deliberate price" in impact["blast_radius"]
    assert doc["failure_policy"]["on_failure"] == "fail-fast"
