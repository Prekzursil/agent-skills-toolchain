"""FLAGSHIP end-to-end test for `anchor-checked-per-file-deploy` (bp-8, slot 89, BP-REL-03).

Mechanism claims under test: apply order is the defect, so the fan-out runs at concurrency 1 and
aborts on the first item failure; each file's anchor is a BLOCKING PRECONDITION enforced by a real
gate stage placed between the pre-image capture and the write; the postcondition is a named SYMBOL
asserted by a CROSS-VENDOR role and explicitly NOT a green test suite (the recorded case reached
681 passed in both apply orders, one of which had deleted the fix); an installer that reports
``{status: deployed, count: 0}`` with exit 0 is a detected fail-open, not a success; and the owner
checkpoint FAILS on timeout so a deploy can never become authorised by nobody answering.

`check_the_anchor_gate_is_actually_wired_to_a_stage` is here because this suite MEASURED the
defect it guards: as shipped, ``anchor-present`` was declared ``blocking: true, on_fail: fail`` in
the ``gates`` map and referenced by NO stage, so the blueprint's headline precondition enforced
nothing. ``wfdsl.semantics`` reported 0 advisories on the document in that state, so neither the
schema nor the semantic layer could see it. Fixed by wiring stage ``gate-anchor``; the mutation
control below unwires it again and requires this check to fail.
"""

from __future__ import annotations

from typing import Any, Mapping

import bp8_testkit as K
import pytest

WORKFLOW_ID = "anchor-checked-per-file-deploy"
DOC = K.load(WORKFLOW_ID)
BODY_ORDER = (
    "capture-baseline",
    "gate-anchor",
    "check-anchor-and-write",
    "assert-symbol",
)


# ------------------------------------------------------------------------------- the checks


def check_apply_order_is_serial_and_aborts_on_failure(doc: Mapping[str, Any]) -> None:
    fan = K.fanout(doc, "apply-serially")
    assert fan["max_concurrency"] == 1, (
        "apply order is load-bearing: a bundle applied after a targeted fix deletes that fix"
    )
    assert fan["on_item_failure"] == "abort", (
        "continuing past a failed item applies later files on top of a known-bad state"
    )
    assert fan["over"]["key_field"] == "order", (
        "the item key must be the declared apply order"
    )
    assert fan["over"]["ref"] == "apply_plan"


def check_the_anchor_gate_is_actually_wired_to_a_stage(doc: Mapping[str, Any]) -> None:
    spec = K.gate_for_stage(doc, "gate-anchor")
    assert "anchor_found == true" in spec["expression"]
    assert "target_baseline_captured == true" in spec["expression"], (
        "an anchor match without a recorded pre-image is an irreversible write"
    )
    assert spec["blocking"] is True and spec["on_fail"] == "fail"
    # the gate must be reachable in the fan-out body, between the capture and the write
    body_ids = [str(st["id"]) for st in K.fanout(doc, "apply-serially")["body"]]
    K.assert_precedes(body_ids, "capture-baseline", "gate-anchor")
    K.assert_precedes(body_ids, "gate-anchor", "check-anchor-and-write")
    assert K.depends_on(doc, "check-anchor-and-write") == ["gate-anchor"], (
        "the write must be reachable only through the anchor gate"
    )


def check_no_gate_is_declared_but_unenforced(doc: Mapping[str, Any]) -> None:
    """The general form of the measured defect: an orphaned gate blocks nothing."""
    enforced = {
        str(st.get("gate_ref"))
        for _, st in K.stages(doc)
        if st.get("kind") == "gate" and st.get("gate_ref")
    }
    declared = set(doc.get("gates") or {})
    assert declared - enforced == set(), (
        f"gates declared but enforced by no stage: {sorted(declared - enforced)}"
    )
    assert enforced - declared == set(), (
        f"stages point at undeclared gates: {sorted(enforced - declared)}"
    )


def check_the_postcondition_is_a_symbol_not_a_green_suite(
    doc: Mapping[str, Any],
) -> None:
    spec = K.gate_for_stage(doc, "gate-symbol")
    assert "asserted_symbol_present == true" in spec["expression"]
    assert "symbol_assertion_is_independent_of_suite == true" in spec["expression"], (
        "the recorded case was 681 passed in BOTH apply orders; a green suite is not the oracle"
    )
    assert spec["on_fail"] == "escalate-to-human"
    ids = {c["id"] for c in K.benchmark_cases(doc)}
    assert "symbol-assertion-catches-what-the-suite-misses" in ids


def check_the_postcondition_auditor_is_cross_vendor_with_a_veto(
    doc: Mapping[str, Any],
) -> None:
    auditor = doc["roles"]["postcondition-auditor"]
    operator = doc["roles"]["deploy-operator"]
    assert auditor["vendor"] != operator["vendor"], (
        "the operator wrote the bytes; a same-vendor auditor shares its blind spot"
    )
    assert auditor.get("cross_vendor_required") is True
    assert auditor["authority"] == "veto", (
        "an advisory postcondition is not a postcondition"
    )
    routes = K.routes_for(doc, "postcondition-auditor")
    assert routes and routes[0]["target"]["vendor"] != operator["vendor"]
    assert K.stage(doc, "assert-symbol")["role"] == "postcondition-auditor"


def check_the_barrier_rejects_a_receipt_as_a_result(doc: Mapping[str, Any]) -> None:
    spec = K.barrier(doc, "apply-serially")
    K.assert_rejects_fire_and_forget(spec)
    assert spec["mode"] == "all"
    assert spec["on_partial"] == "fail", (
        "a partially applied per-file deploy is not a degraded success"
    )
    assert "assert-symbol" in spec["require_stages"], (
        "the barrier must require the postcondition stage, not merely the write"
    )


def check_the_fail_open_installer_shape_is_detected(doc: Mapping[str, Any]) -> None:
    rule = K.stopping_rule(doc, "fail-open-detected")
    assert "reported_deployed_count == 0" in rule["expression"]
    assert "reported_status == DEPLOYED" in rule["expression"]
    assert rule["on_stop"] == "escalate"
    assert "fail-open-zero-count" in doc["failure_policy"]["classify_as"]


def check_the_installer_ban_is_enforced_by_code_not_memory(
    doc: Mapping[str, Any],
) -> None:
    spec = doc["params"]["installer_transport_banned"]
    assert spec["type"] == "boolean" and spec["default"] is True
    gate_spec = K.gate_for_stage(doc, "gate-preservation")
    assert "installer_transport_banned == true" in gate_spec["expression"], (
        "a procedural ban nobody checks is a memo, not a control"
    )
    assert "preservation_table_entries > 0" in gate_spec["expression"]
    assert doc["params"]["live_unique_preservation_table"]["min_items"] >= 1


def check_the_owner_checkpoint_fails_on_timeout(doc: Mapping[str, Any]) -> None:
    st = K.stage(doc, "owner-authorise-deploy")
    assert st["kind"] == "human_checkpoint"
    assert st["approval_mode"] == "owner-only"
    assert st["on_timeout"] == "fail", (
        "a write into a live tree must never become authorised by a timeout"
    )
    order = K.top_level_stage_ids(doc)
    K.assert_precedes(order, "gate-preservation", "owner-authorise-deploy")
    K.assert_precedes(order, "owner-authorise-deploy", "apply-serially")


def check_an_anchor_or_symbol_failure_is_never_retried(doc: Mapping[str, Any]) -> None:
    no_retry = set(doc["retry_policy"]["no_retry_on"])
    assert {
        "anchor-mismatch",
        "symbol-absent",
        "restore-hash-mismatch",
        "missing-preimage",
    } <= no_retry, (
        "retrying a refused write is how a precondition gets worn down into a warning"
    )
    assert doc["retry_policy"]["pivot"]["enumerate_alternatives_min"] >= 2


def check_a_resume_cannot_reorder_the_apply(doc: Mapping[str, Any]) -> None:
    resume = doc["resume"]
    assert resume["granularity"] == "fanout-item"
    assert "item_key" in resume["idempotency_key_from"], (
        "without the item key a resumed deploy cannot know which file it already wrote"
    )
    assert resume["on_stale"] == "fail", (
        "a stale checkpoint plus a moved live tree is exactly the wrong-order case"
    )


def check_the_peer_owned_trees_are_unwritable(doc: Mapping[str, Any]) -> None:
    forbidden = set(doc["tool_policy"]["forbid_write_paths"])
    assert "Documents/GitHub/Reframe/**" in forbidden
    assert ".claude/agent-worktrees/**" in forbidden
    assert doc["tool_policy"]["default"] == "deny"
    assert "Bash" in doc["tool_policy"]["deny"]
    assert (
        "Write(command-center/deploy/**)"
        in doc["tool_policy"]["require_owner_approval"]
    )


def check_the_worked_example_applies_in_declared_order(doc: Mapping[str, Any]) -> None:
    example = K.worked_examples(doc)[0]
    plan = example["params"]["apply_plan"]
    orders = [item["order"] for item in plan]
    assert orders == sorted(orders), (
        "the worked example must apply in ascending declared order"
    )
    for item in plan:
        assert item["expected_anchor"], "every planned file needs an anchor"
        assert item["asserted_symbol"], (
            "every planned file needs a postcondition symbol"
        )
    trace = example["apply_trace"]
    assert len(trace) == len(plan), "the trace must cover every planned file"
    for row in trace:
        assert row["preimage_hash"] and row["postwrite_hash"]
        assert row["preimage_hash"] != row["postwrite_hash"], (
            "a write that did not change the bytes is the zero-count fail-open shape"
        )
    assert example["params"]["installer_transport_banned"] is True


ALL_CHECKS = (
    check_apply_order_is_serial_and_aborts_on_failure,
    check_the_anchor_gate_is_actually_wired_to_a_stage,
    check_no_gate_is_declared_but_unenforced,
    check_the_postcondition_is_a_symbol_not_a_green_suite,
    check_the_postcondition_auditor_is_cross_vendor_with_a_veto,
    check_the_barrier_rejects_a_receipt_as_a_result,
    check_the_fail_open_installer_shape_is_detected,
    check_the_installer_ban_is_enforced_by_code_not_memory,
    check_the_owner_checkpoint_fails_on_timeout,
    check_an_anchor_or_symbol_failure_is_never_retried,
    check_a_resume_cannot_reorder_the_apply,
    check_the_peer_owned_trees_are_unwritable,
    check_the_worked_example_applies_in_declared_order,
)


@pytest.mark.parametrize("check", ALL_CHECKS, ids=lambda c: c.__name__)
def test_shipped_blueprint_satisfies_every_mechanism_check(check: Any) -> None:
    check(DOC)


def test_shipped_blueprint_is_conformant() -> None:
    assert K.schema_errors(DOC) == []
    assert K.semantic_violations(DOC) == []
    assert K.blueprint_meta(DOC)["slot"] == 89
    assert K.blueprint_meta(DOC)["design_card"] == "BP-REL-03"
    assert DOC["flagship"] is True


def test_the_fanout_body_order_is_the_declared_pipeline() -> None:
    body_ids = tuple(str(st["id"]) for st in K.fanout(DOC, "apply-serially")["body"])
    assert body_ids == BODY_ORDER, f"the per-file pipeline changed shape: {body_ids}"


# ------------------------------------------------------------------------- mutation controls


def _parallelise_the_apply(doc: dict) -> None:
    K.find_stage_mut(doc, "apply-serially")["max_concurrency"] = 8


def _unwire_the_anchor_gate(doc: dict) -> None:
    """Restore the measured defect exactly: the gate stays declared, no stage enforces it."""
    fan = K.find_stage_mut(doc, "apply-serially")
    fan["body"] = [st for st in fan["body"] if st["id"] != "gate-anchor"]
    for st in fan["body"]:
        if st["id"] == "check-anchor-and-write":
            st["depends_on"] = ["capture-baseline"]


def _declare_an_extra_orphan_gate(doc: dict) -> None:
    doc["gates"]["looks-enforced-but-is-not"] = {
        "predicate": "custom-expression",
        "expression": "everything_is_fine == true",
        "blocking": True,
        "evidence_required": True,
        "on_fail": "fail",
    }


def _accept_a_green_suite_as_the_postcondition(doc: dict) -> None:
    doc["gates"]["symbol-asserted-not-suite-green"]["expression"] = (
        "asserted_symbol_present == true"
    )


def _make_the_auditor_same_vendor(doc: dict) -> None:
    doc["roles"]["postcondition-auditor"]["vendor"] = doc["roles"]["deploy-operator"][
        "vendor"
    ]


def _accept_a_background_receipt(doc: dict) -> None:
    K.find_stage_mut(doc, "apply-serially")["barrier"]["reject_result_matching"] = [
        "ERROR"
    ]


def _drop_the_fail_open_rule(doc: dict) -> None:
    doc["stopping_rules"] = [
        r for r in doc["stopping_rules"] if r["id"] != "fail-open-detected"
    ]


def _default_the_installer_ban_off(doc: dict) -> None:
    doc["params"]["installer_transport_banned"]["default"] = False


def _let_the_deploy_authorise_itself_on_timeout(doc: dict) -> None:
    K.find_stage_mut(doc, "owner-authorise-deploy")["on_timeout"] = "proceed"


def _retry_an_anchor_mismatch(doc: dict) -> None:
    doc["retry_policy"]["no_retry_on"] = ["restore-hash-mismatch"]


def _resume_without_the_item_key(doc: dict) -> None:
    doc["resume"]["idempotency_key_from"] = ["workflow_id", "stage_id"]


def _allow_writes_into_a_peer_tree(doc: dict) -> None:
    doc["tool_policy"]["forbid_write_paths"] = ["platform/schema/**"]


def _scramble_the_worked_example_order(doc: dict) -> None:
    plan = doc["x_extensions"]["worked_examples"][0]["params"]["apply_plan"]
    plan.reverse()


MUTATIONS = (
    (check_apply_order_is_serial_and_aborts_on_failure, _parallelise_the_apply),
    (check_the_anchor_gate_is_actually_wired_to_a_stage, _unwire_the_anchor_gate),
    (check_no_gate_is_declared_but_unenforced, _declare_an_extra_orphan_gate),
    (
        check_the_postcondition_is_a_symbol_not_a_green_suite,
        _accept_a_green_suite_as_the_postcondition,
    ),
    (
        check_the_postcondition_auditor_is_cross_vendor_with_a_veto,
        _make_the_auditor_same_vendor,
    ),
    (check_the_barrier_rejects_a_receipt_as_a_result, _accept_a_background_receipt),
    (check_the_fail_open_installer_shape_is_detected, _drop_the_fail_open_rule),
    (
        check_the_installer_ban_is_enforced_by_code_not_memory,
        _default_the_installer_ban_off,
    ),
    (
        check_the_owner_checkpoint_fails_on_timeout,
        _let_the_deploy_authorise_itself_on_timeout,
    ),
    (check_an_anchor_or_symbol_failure_is_never_retried, _retry_an_anchor_mismatch),
    (check_a_resume_cannot_reorder_the_apply, _resume_without_the_item_key),
    (check_the_peer_owned_trees_are_unwritable, _allow_writes_into_a_peer_tree),
    (
        check_the_worked_example_applies_in_declared_order,
        _scramble_the_worked_example_order,
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


def test_the_unwired_gate_mutant_is_schema_legal_and_violation_free() -> None:
    """The measured defect in its exact shape - valid DSL, zero semantic violations, unenforced.

    This is the proof that the schema and semantic layers could not see it, and that only this
    suite rejects it. If this test ever starts failing because ``semantic_violations`` is
    non-empty, ``wfdsl.semantics`` grew an orphan-gate rule and this check became redundant -
    which would be good news, not a regression.
    """
    broken = K.mutant(DOC, _unwire_the_anchor_gate)
    assert K.schema_errors(broken) == []
    assert K.semantic_violations(broken) == []
    assert K.raises_assertion(
        check_the_anchor_gate_is_actually_wired_to_a_stage, broken
    )
    assert K.raises_assertion(check_no_gate_is_declared_but_unenforced, broken)
