"""FLAGSHIP end-to-end test for `pr-shepherd-to-merge` (bp-8, slot 87, design BP-REL-01).

Mechanism claims under test - each is a MEASURED misreading this blueprint exists to prevent:
`mergeStateStatus: BLOCKED` means the checks RAN AND FAILED, not that they are pending; a `gh`
auth or rate-limit error is a DETECTOR failure and never a verdict; a job stops at its FIRST
failing step, so the loop's progress signal is "the failure TEXT changed" and the loop must be
unable to converge by exhausting its round budget; `mergeStateStatus: UNKNOWN` is not mergeable;
and the merge itself is an owner-only checkpoint that must not become authorised by a timeout.

Every check ships with a targeted mutant (``MUTATIONS``) and is asserted to FAIL on it. A check
that is silent on both the shipped document and the mutant measures nothing.
"""

from __future__ import annotations

from typing import Any, Mapping

import bp8_testkit as K
import pytest

WORKFLOW_ID = "pr-shepherd-to-merge"
DOC = K.load(WORKFLOW_ID)


# ------------------------------------------------------------------------------- the checks


def check_blocked_is_decoded_as_ran_and_failed(doc: Mapping[str, Any]) -> None:
    spec = K.gate_for_stage(doc, "gate-decoded")
    for clause in (
        "status_source == API",
        "blocked_decoded_as_ran_and_failed == true",
        "detector_error == false",
    ):
        assert clause in spec["expression"], (
            f"the decode gate does not assert {clause!r}"
        )
    assert spec["blocking"] is True and spec["on_fail"] == "fail"
    assert spec.get("evidence_required") is True, (
        "a decoded status must carry its evidence"
    )


def check_a_detector_error_is_never_a_verdict(doc: Mapping[str, Any]) -> None:
    spec = K.gate_for_stage(doc, "gate-detector")
    assert "NOT auth_error" in spec["expression"]
    assert "NOT rate_limited" in spec["expression"]
    assert spec["blocking"] is True
    assert spec["on_fail"] == "escalate-to-human", (
        "a broken instrument must reach a human, not silently produce a zero-checks report"
    )
    rule = K.stopping_rule(doc, "detector-broke")
    assert rule["on_stop"] == "emit-partial", (
        "a detector failure may not terminate as 'complete' - that is the fail-open shape"
    )
    K.assert_precedes(K.top_level_stage_ids(doc), "gate-detector", "gate-decoded")


def check_the_detector_gate_runs_before_any_fixing(doc: Mapping[str, Any]) -> None:
    order = K.top_level_stage_ids(doc)
    K.assert_precedes(order, "gate-detector", "fix-rounds")
    K.assert_precedes(order, "gate-decoded", "fix-rounds")
    assert K.depends_on(doc, "fix-rounds") == ["gate-decoded"], (
        "the fix loop must be reachable only through the decoding gates"
    )


def check_progress_is_the_failure_text_changing(doc: Mapping[str, Any]) -> None:
    conv = K.stage(doc, "fix-rounds")["convergence"]
    metrics = {m["name"] for m in conv["metrics"]}
    assert "distinct_failure_texts_this_round" in metrics, (
        "one red job hides N stacked failures; the progress signal is a CHANGED failure text"
    )
    assert "distinct_failure_texts_this_round == 0" in conv["converged_when"]
    assert "required_contexts_failing == 0" in conv["converged_when"]


def check_the_loop_cannot_converge_by_exhausting_its_budget(
    doc: Mapping[str, Any],
) -> None:
    conv = K.stage(doc, "fix-rounds")["convergence"]
    assert conv["on_no_convergence"] == "escalate", (
        "running out of rounds is not convergence"
    )
    assert conv["no_progress_rounds"] < conv["max_iterations"], (
        "the no-progress exit must fire before the round budget, or grinding is the default"
    )
    rule = K.stopping_rule(doc, "same-fingerprint-twice")
    assert "identical_failure_fingerprint_count >= 2" in rule["expression"]
    assert rule["applies_to"] == "loop" and rule["on_stop"] == "escalate"


def check_only_required_contexts_gate_and_unknown_is_not_mergeable(
    doc: Mapping[str, Any],
) -> None:
    spec = K.gate_for_stage(doc, "gate-required-green")
    for clause in (
        "required_contexts_failing == 0",
        "required_contexts_pending == 0",
        "merge_state_status != UNKNOWN",
    ):
        assert clause in spec["expression"], (
            f"the merge gate does not assert {clause!r}"
        )
    assert doc["params"]["required_contexts"]["min_items"] >= 1, (
        "with no required contexts declared the gate is vacuous"
    )


def check_the_merge_is_an_owner_only_checkpoint(doc: Mapping[str, Any]) -> None:
    st = K.stage(doc, "owner-merge-decision")
    assert st["kind"] == "human_checkpoint"
    assert st["approval_mode"] == "owner-only"
    assert st["on_timeout"] != "proceed", (
        "a merge must never become authorised because nobody answered"
    )
    assert "close-without-merging" in st["options"], (
        "closing is a legitimate terminal state, not a shepherding failure"
    )


def check_the_shepherd_cannot_rewrite_the_gate_judging_it(
    doc: Mapping[str, Any],
) -> None:
    policy = doc["tool_policy"]
    assert policy["default"] == "deny"
    assert ".github/workflows/**" in policy["forbid_write_paths"], (
        "editing the CI definition is how a red gate is made to pass without a fix"
    )
    assert "Bash:gh" in policy["require_owner_approval"]
    assert "Bash" in policy["deny"], (
        "unrestricted shell would bypass every allow-listed verb"
    )


def check_the_reviewer_is_cross_vendor(doc: Mapping[str, Any]) -> None:
    critic = doc["roles"]["cross-vendor-critic"]
    shepherd = doc["roles"]["shepherd"]
    assert critic["vendor"] != shepherd["vendor"], (
        "a same-vendor reviewer shares the author's blind spots"
    )
    assert critic.get("cross_vendor_required") is True
    routes = K.routes_for(doc, "cross-vendor-critic")
    assert routes, "the cross-vendor role must be pinned by a routing rule, not by hope"
    assert routes[0]["target"]["vendor"] != shepherd["vendor"]


def check_ci_status_is_never_served_from_cache(doc: Mapping[str, Any]) -> None:
    assert doc["cache"]["enabled"] is False, (
        "a cached CI status certifies a run that has since changed"
    )
    forbidden = set(doc["dry_run"]["forbid_tools"])
    assert {"Bash:gh", "Bash:git"} <= forbidden, (
        "a dry run must not touch the hosted PR"
    )
    assert doc["dry_run"]["side_effect_free"] is True


def check_failure_is_always_terminal_and_named(doc: Mapping[str, Any]) -> None:
    policy = doc["failure_policy"]
    assert policy["terminal_state_required"] is True
    assert policy["never_silent"] is True
    assert "detector-failure" in policy["classify_as"]
    assert policy["preserve_partial_artifact"] is True
    rule = K.stopping_rule(doc, "merged-or-named-block")
    assert "blocked_reason_named == true" in rule["expression"], (
        "'blocked' without a named reason is not a terminal state"
    )
    assert "detector_error == false" in rule["minimum_conditions"]


def check_the_worked_example_shows_stacked_failures(doc: Mapping[str, Any]) -> None:
    example = K.worked_examples(doc)[0]
    rounds = example["rounds"]
    assert len(rounds) >= 3, (
        "the measured incident was FOUR stacked failures in one red job"
    )
    texts = [r["failure_text"] for r in rounds]
    assert len(set(texts)) == len(texts), (
        "each round must surface a DIFFERENT failure text, or the example contradicts the mechanism"
    )
    assert example["params"]["required_contexts"], (
        "a worked example must bind every required param"
    )
    ids = {c["id"] for c in K.benchmark_cases(doc)}
    assert "blocked-is-not-pending" in ids
    assert "auth-error-is-a-detector-failure" in ids


ALL_CHECKS = (
    check_blocked_is_decoded_as_ran_and_failed,
    check_a_detector_error_is_never_a_verdict,
    check_the_detector_gate_runs_before_any_fixing,
    check_progress_is_the_failure_text_changing,
    check_the_loop_cannot_converge_by_exhausting_its_budget,
    check_only_required_contexts_gate_and_unknown_is_not_mergeable,
    check_the_merge_is_an_owner_only_checkpoint,
    check_the_shepherd_cannot_rewrite_the_gate_judging_it,
    check_the_reviewer_is_cross_vendor,
    check_ci_status_is_never_served_from_cache,
    check_failure_is_always_terminal_and_named,
    check_the_worked_example_shows_stacked_failures,
)


@pytest.mark.parametrize("check", ALL_CHECKS, ids=lambda c: c.__name__)
def test_shipped_blueprint_satisfies_every_mechanism_check(check: Any) -> None:
    check(DOC)


def test_shipped_blueprint_is_conformant() -> None:
    assert K.schema_errors(DOC) == []
    assert K.semantic_violations(DOC) == []
    assert K.blueprint_meta(DOC)["slot"] == 87
    assert K.blueprint_meta(DOC)["design_card"] == "BP-REL-01"
    assert DOC["flagship"] is True


# ------------------------------------------------------------------------- mutation controls


def _treat_blocked_as_pending(doc: dict) -> None:
    doc["gates"]["status-decoded-not-guessed"]["expression"] = "status_source == API"


def _let_an_auth_error_pass(doc: dict) -> None:
    doc["gates"]["detector-not-verdict"]["expression"] = "NOT rate_limited"
    K.stopping_rule(doc, "detector-broke")  # still present; only the gate is weakened
    for rule in doc["stopping_rules"]:
        if rule["id"] == "detector-broke":
            rule["on_stop"] = "complete"


def _let_the_loop_run_before_the_gates(doc: dict) -> None:
    K.find_stage_mut(doc, "fix-rounds")["depends_on"] = ["read-real-status"]


def _drop_the_failure_text_metric(doc: dict) -> None:
    conv = K.find_stage_mut(doc, "fix-rounds")["convergence"]
    conv["metrics"] = [
        m for m in conv["metrics"] if m["name"] != "distinct_failure_texts_this_round"
    ]
    conv["converged_when"] = "required_contexts_failing == 0"


def _let_budget_exhaustion_count_as_convergence(doc: dict) -> None:
    conv = K.find_stage_mut(doc, "fix-rounds")["convergence"]
    conv["on_no_convergence"] = "complete"
    conv["no_progress_rounds"] = 12


def _accept_unknown_as_mergeable(doc: dict) -> None:
    doc["gates"]["required-contexts-green"]["expression"] = (
        "required_contexts_failing == 0 AND required_contexts_pending == 0"
    )


def _let_the_merge_proceed_on_timeout(doc: dict) -> None:
    K.find_stage_mut(doc, "owner-merge-decision")["on_timeout"] = "proceed"


def _allow_workflow_file_writes(doc: dict) -> None:
    doc["tool_policy"]["forbid_write_paths"] = ["command-center/WORK-UNIT-CATALOG.json"]


def _make_the_critic_same_vendor(doc: dict) -> None:
    doc["roles"]["cross-vendor-critic"]["vendor"] = doc["roles"]["shepherd"]["vendor"]


def _enable_the_cache(doc: dict) -> None:
    doc["cache"]["enabled"] = True


def _allow_a_silent_failure(doc: dict) -> None:
    doc["failure_policy"]["never_silent"] = False
    doc["failure_policy"]["terminal_state_required"] = False


def _collapse_the_worked_example_to_one_repeated_text(doc: dict) -> None:
    rounds = doc["x_extensions"]["worked_examples"][0]["rounds"]
    for r in rounds:
        r["failure_text"] = "something broke"


MUTATIONS = (
    (check_blocked_is_decoded_as_ran_and_failed, _treat_blocked_as_pending),
    (check_a_detector_error_is_never_a_verdict, _let_an_auth_error_pass),
    (
        check_the_detector_gate_runs_before_any_fixing,
        _let_the_loop_run_before_the_gates,
    ),
    (check_progress_is_the_failure_text_changing, _drop_the_failure_text_metric),
    (
        check_the_loop_cannot_converge_by_exhausting_its_budget,
        _let_budget_exhaustion_count_as_convergence,
    ),
    (
        check_only_required_contexts_gate_and_unknown_is_not_mergeable,
        _accept_unknown_as_mergeable,
    ),
    (check_the_merge_is_an_owner_only_checkpoint, _let_the_merge_proceed_on_timeout),
    (
        check_the_shepherd_cannot_rewrite_the_gate_judging_it,
        _allow_workflow_file_writes,
    ),
    (check_the_reviewer_is_cross_vendor, _make_the_critic_same_vendor),
    (check_ci_status_is_never_served_from_cache, _enable_the_cache),
    (check_failure_is_always_terminal_and_named, _allow_a_silent_failure),
    (
        check_the_worked_example_shows_stacked_failures,
        _collapse_the_worked_example_to_one_repeated_text,
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


def test_the_blocked_as_pending_mutant_is_schema_legal() -> None:
    """The defect's exact shape: still valid DSL, still violation-free, only this test rejects it."""
    broken = K.mutant(DOC, _treat_blocked_as_pending)
    assert K.schema_errors(broken) == []
    assert K.semantic_violations(broken) == []
    assert K.raises_assertion(check_blocked_is_decoded_as_ran_and_failed, broken)
