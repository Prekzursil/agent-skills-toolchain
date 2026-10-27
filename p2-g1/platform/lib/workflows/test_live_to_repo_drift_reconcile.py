"""FLAGSHIP end-to-end test for `live-to-repo-drift-reconcile` (bp-8, slot 92, BP-MNT-01).

Mechanism claims under test: the workflow DISTRUSTS ITS OWN TOOL FIRST - stage ``control-the-tool``
has no predecessor, and everything else is reachable only through a gate that requires the control
to have produced DIFFERENT outcomes in the broken and the fixed state (a probe silent in both
states measures nothing); a CLEAN verdict harvested from a WRITING run is refused, because the
measured footgun is a report-format flag that writes; the deterministic blob classification is
DELEGATED to the ``dual-tree-plumbing-mirror`` subworkflow rather than reimplemented, so the
platform holds exactly one classifier; a two-sided file goes to a max-effort two-directional merge
whose postcondition is that BOTH sides' unique lines survive; and the owner - not the workflow -
picks the branch that carries the reconciliation.

Every check ships with a targeted mutant and is asserted to FAIL on it.
"""

from __future__ import annotations

from typing import Any, Mapping

import bp8_testkit as K
import pytest

WORKFLOW_ID = "live-to-repo-drift-reconcile"
DOC = K.load(WORKFLOW_ID)


# ------------------------------------------------------------------------------- the checks


def check_the_tool_control_is_the_first_thing_that_runs(doc: Mapping[str, Any]) -> None:
    first = doc["stages"][0]
    assert first["id"] == "control-the-tool", (
        "distrust-the-tool-first is the mechanism; anything before it inherits the tool's hazard"
    )
    assert not first.get("depends_on"), "the control must have no predecessor"
    order = K.top_level_stage_ids(doc)
    K.assert_precedes(order, "control-the-tool", "gate-control")
    K.assert_precedes(order, "gate-control", "classify-drift")
    assert K.depends_on(doc, "stage-repo-first") == ["gate-control"], (
        "every later stage must be reachable only through the control gate"
    )


def check_the_control_requires_different_outcomes_in_both_states(
    doc: Mapping[str, Any],
) -> None:
    spec = K.gate_for_stage(doc, "gate-control")
    assert "control_fired_in_broken_state == true" in spec["expression"]
    assert "control_silent_in_fixed_state == true" in spec["expression"], (
        "a probe that fires in both states, or is silent in both, measures nothing"
    )
    assert spec["blocking"] is True and spec["on_fail"] == "fail"
    rule = K.stopping_rule(doc, "control-inconclusive")
    assert rule["on_stop"] == "escalate", "an inconclusive control is not a pass"
    complete = K.stopping_rule(doc, "unresolved-empty-or-deferred")
    assert "control_fired_in_broken_state == true" in complete["minimum_conditions"], (
        "completion must be conditioned on the control, not merely preceded by it"
    )


def check_the_control_is_run_in_a_scratch_copy(doc: Mapping[str, Any]) -> None:
    spec = doc["params"]["scratch_copy_root"]
    # .get, not [], so a DELETED key fails as an AssertionError rather than a KeyError - a
    # KeyError escapes the both-states control as an error instead of a detected defect
    assert spec.get("type") == "path" and spec.get("required") is True, (
        "the control deliberately destroys an edit; it must never do that in the real tree"
    )
    ids = {c["id"] for c in K.benchmark_cases(doc)}
    assert "destroy-an-uncommitted-edit" in ids
    assert "scratch-copy-missing" in doc["retry_policy"]["retry_on"]


def check_a_clean_verdict_from_a_writing_run_is_refused(doc: Mapping[str, Any]) -> None:
    spec = K.gate_for_stage(doc, "gate-verdict-provenance")
    assert "verdict_source_run_was_nonwriting == true" in spec["expression"]
    assert "NOT clean_verdict_from_writing_run" in spec["expression"], (
        "the measured footgun is a report-format flag that WRITES; its CLEAN is not evidence"
    )
    assert spec["blocking"] is True and spec["on_fail"] == "fail"
    assert "clean-verdict-from-writing-run" in doc["failure_policy"]["classify_as"]
    K.assert_precedes(
        K.top_level_stage_ids(doc), "emit-drift-report", "gate-verdict-provenance"
    )


def check_apply_mode_is_gated_on_a_clean_repo(doc: Mapping[str, Any]) -> None:
    spec = K.gate_for_stage(doc, "gate-clean")
    assert "mode == drift" in spec["expression"]
    assert "repo_uncommitted_paths == 0" in spec["expression"], (
        "applying over uncommitted repo work is the data-loss path this gate exists for"
    )
    assert doc["params"]["mode"]["default"] == "drift", (
        "the read-only mode is the safe default"
    )
    assert doc["params"]["allow_apply_with_dirty_repo"]["default"] is False


def check_classification_is_delegated_not_reimplemented(doc: Mapping[str, Any]) -> None:
    st = K.stage(doc, "classify-drift")
    assert st["kind"] == "subworkflow"
    child = st["workflow"]["workflow_id"]
    assert child == "dual-tree-plumbing-mirror"
    declared = doc["subworkflows"][child]
    assert declared["workflow_id"] == child
    source = K.REPO_ROOT / declared["source"]
    assert source.is_file(), (
        f"the declared child source is absent: {declared['source']}"
    )
    assert declared["version_range"], (
        "a child must be pinned to a compatible version range"
    )
    reason = K.ext(doc, "not_a_duplicate_because")
    assert "vs_dual-tree-plumbing-mirror" in reason, (
        "the delegation must be justified against the primitive it calls"
    )


def check_a_two_sided_merge_gets_maximum_effort(doc: Mapping[str, Any]) -> None:
    routes = K.routes_for(doc, "hand-merge-two-sided")
    assert routes, "the merge stage must be pinned by a routing rule"
    assert routes[0]["target"]["effort"] == "max", (
        "a merge that drops one side's unique lines is unrecoverable loss"
    )
    assert doc["model_routing"]["forbid_downgrade_below"] == "opus"
    assert doc["roles"]["merge-author"]["effort"] == "max"


def check_the_merge_postcondition_needs_every_term(doc: Mapping[str, Any]) -> None:
    rule = K.stopping_rule(doc, "weighted-reconcile-quality")
    weighted = rule["expression"]["weighted"]
    terms = {t["expr"]: t["weight"] for t in weighted["terms"]}
    assert "unique_line_assertion_passed == true" in terms
    assert "verdict_source_run_was_nonwriting == true" in terms
    assert abs(sum(terms.values()) - weighted["threshold"]) < 1e-9, (
        "a threshold below the term total lets the reconcile pass while dropping a side"
    )
    assert terms["unique_line_assertion_passed == true"] >= 0.5, (
        "the both-sides-survive term must be the dominant one"
    )


def check_a_one_directional_merge_is_never_retried(doc: Mapping[str, Any]) -> None:
    no_retry = set(doc["retry_policy"]["no_retry_on"])
    assert {
        "one-directional-merge",
        "unique-line-lost",
        "probe-silent-in-both-states",
    } <= no_retry, "retrying a merge that already lost a line cannot recover it"
    assert doc["retry_policy"]["pivot"]["enumerate_alternatives_min"] >= 2
    assert doc["failure_policy"]["on_failure"] == "quarantine"
    assert doc["failure_policy"]["preserve_partial_artifact"] is True


def check_the_completion_predicate_is_the_full_twelve_conditions(
    doc: Mapping[str, Any],
) -> None:
    spec = K.gate_for_stage(doc, "gate-unit-complete")
    assert spec["predicate"] == "completion-predicate-v1"
    assert spec["conditions_required"] == list(range(1, 13)), (
        "a subset of the completion predicate is a partial gate presented as a whole one"
    )
    resolved = K.resolve_schema_reference(spec["predicate_ref"])
    assert resolved is not None and resolved.is_file(), (
        f"the predicate reference does not resolve on disk: {spec['predicate_ref']}"
    )


def check_the_owner_picks_the_branch(doc: Mapping[str, Any]) -> None:
    st = K.stage(doc, "owner-branch-decision")
    assert st["kind"] == "human_checkpoint"
    assert st["approval_mode"] == "owner-only"
    assert st["on_timeout"] == "fail"
    assert "defer-unresolved-set" in st["options"], (
        "deferring an unresolved set is a legitimate outcome and must be offered"
    )
    order = K.top_level_stage_ids(doc)
    K.assert_precedes(order, "gate-unit-complete", "owner-branch-decision")


def check_the_peer_owned_trees_are_unwritable(doc: Mapping[str, Any]) -> None:
    policy = doc["tool_policy"]
    assert policy["default"] == "deny"
    assert policy["network"] == "none"
    forbidden = set(policy["forbid_write_paths"])
    assert "Documents/GitHub/Reframe/**" in forbidden
    assert ".claude/agent-worktrees/**" in forbidden
    assert "Bash:pwsh" in policy["require_owner_approval"], (
        "the hazardous tool must not be callable without owner approval"
    )


def check_the_worked_example_records_both_control_states(
    doc: Mapping[str, Any],
) -> None:
    example = K.worked_examples(doc)[0]
    control = example["control_result"]
    assert "broken_state_run" in control and "fixed_state_run" in control, (
        "a worked example that shows only one state cannot demonstrate the mechanism"
    )
    assert control["verdict"].startswith("PASS")
    classification = example["classification"]
    assert classification["eol_only"] > 0, (
        "the EOL-only bucket is what a naive comparison misreports as drift"
    )
    assert classification["two_sided"] > 0, (
        "the two-sided bucket is the one a one-directional check silently overwrites"
    )
    assert example["params"]["mode"] == "drift"


def check_the_unverified_claims_name_their_settling_experiment(
    doc: Mapping[str, Any],
) -> None:
    claims = K.ext(doc, "unverified")
    assert claims, (
        "a blueprint quoting measured evidence it did not re-measure must say so"
    )
    for claim in claims:
        assert "Settling experiment" in claim or "settling experiment" in claim, (
            f"an UNVERIFIED claim with no settling experiment is a hedge: {claim[:80]!r}"
        )


ALL_CHECKS = (
    check_the_tool_control_is_the_first_thing_that_runs,
    check_the_control_requires_different_outcomes_in_both_states,
    check_the_control_is_run_in_a_scratch_copy,
    check_a_clean_verdict_from_a_writing_run_is_refused,
    check_apply_mode_is_gated_on_a_clean_repo,
    check_classification_is_delegated_not_reimplemented,
    check_a_two_sided_merge_gets_maximum_effort,
    check_the_merge_postcondition_needs_every_term,
    check_a_one_directional_merge_is_never_retried,
    check_the_completion_predicate_is_the_full_twelve_conditions,
    check_the_owner_picks_the_branch,
    check_the_peer_owned_trees_are_unwritable,
    check_the_worked_example_records_both_control_states,
    check_the_unverified_claims_name_their_settling_experiment,
)


@pytest.mark.parametrize("check", ALL_CHECKS, ids=lambda c: c.__name__)
def test_shipped_blueprint_satisfies_every_mechanism_check(check: Any) -> None:
    check(DOC)


def test_shipped_blueprint_is_conformant() -> None:
    assert K.schema_errors(DOC) == []
    assert K.semantic_violations(DOC) == []
    assert K.blueprint_meta(DOC)["slot"] == 92
    assert K.blueprint_meta(DOC)["design_card"] == "BP-MNT-01"
    assert DOC["flagship"] is True


# ------------------------------------------------------------------------- mutation controls


def _run_the_classification_before_the_control(doc: dict) -> None:
    K.find_stage_mut(doc, "stage-repo-first")["depends_on"] = ["control-the-tool"]


def _accept_a_control_that_only_fired_once(doc: dict) -> None:
    doc["gates"]["footgun-control-passed"]["expression"] = (
        "control_fired_in_broken_state == true"
    )


def _make_the_scratch_copy_optional(doc: dict) -> None:
    doc["params"]["scratch_copy_root"].pop("required")


def _accept_a_clean_verdict_from_a_writing_run(doc: dict) -> None:
    doc["gates"]["clean-verdict-is-not-evidence"]["expression"] = (
        "verdict_present == true"
    )


def _allow_apply_over_a_dirty_repo_by_default(doc: dict) -> None:
    doc["params"]["allow_apply_with_dirty_repo"]["default"] = True
    doc["gates"]["repo-clean-before-apply"]["expression"] = "mode == drift"


def _inline_the_classifier_instead_of_delegating(doc: dict) -> None:
    st = K.find_stage_mut(doc, "classify-drift")
    st["kind"] = "task"
    st.pop("workflow", None)
    st["role"] = "control-runner"


def _downgrade_the_merge_effort(doc: dict) -> None:
    for route in doc["model_routing"]["routes"]:
        if "hand-merge-two-sided" in str(route.get("when")):
            route["target"]["effort"] = "medium"


def _lower_the_weighted_threshold(doc: dict) -> None:
    for rule in doc["stopping_rules"]:
        if rule["id"] == "weighted-reconcile-quality":
            rule["expression"]["weighted"]["threshold"] = 0.5


def _retry_a_lost_unique_line(doc: dict) -> None:
    doc["retry_policy"]["no_retry_on"] = ["clean-verdict-from-writing-run"]


def _require_only_half_the_completion_predicate(doc: dict) -> None:
    doc["gates"]["unit-complete"]["conditions_required"] = [1, 2, 3, 4, 5, 6]


def _let_the_branch_be_picked_on_timeout(doc: dict) -> None:
    K.find_stage_mut(doc, "owner-branch-decision")["on_timeout"] = "proceed"


def _allow_writes_into_a_peer_tree(doc: dict) -> None:
    doc["tool_policy"]["forbid_write_paths"] = ["platform/schema/**"]


def _drop_the_fixed_state_from_the_worked_example(doc: dict) -> None:
    doc["x_extensions"]["worked_examples"][0]["control_result"].pop("fixed_state_run")


def _strip_the_settling_experiments(doc: dict) -> None:
    doc["x_extensions"]["unverified"] = ["this might not hold"]


MUTATIONS = (
    (
        check_the_tool_control_is_the_first_thing_that_runs,
        _run_the_classification_before_the_control,
    ),
    (
        check_the_control_requires_different_outcomes_in_both_states,
        _accept_a_control_that_only_fired_once,
    ),
    (check_the_control_is_run_in_a_scratch_copy, _make_the_scratch_copy_optional),
    (
        check_a_clean_verdict_from_a_writing_run_is_refused,
        _accept_a_clean_verdict_from_a_writing_run,
    ),
    (
        check_apply_mode_is_gated_on_a_clean_repo,
        _allow_apply_over_a_dirty_repo_by_default,
    ),
    (
        check_classification_is_delegated_not_reimplemented,
        _inline_the_classifier_instead_of_delegating,
    ),
    (check_a_two_sided_merge_gets_maximum_effort, _downgrade_the_merge_effort),
    (check_the_merge_postcondition_needs_every_term, _lower_the_weighted_threshold),
    (check_a_one_directional_merge_is_never_retried, _retry_a_lost_unique_line),
    (
        check_the_completion_predicate_is_the_full_twelve_conditions,
        _require_only_half_the_completion_predicate,
    ),
    (check_the_owner_picks_the_branch, _let_the_branch_be_picked_on_timeout),
    (check_the_peer_owned_trees_are_unwritable, _allow_writes_into_a_peer_tree),
    (
        check_the_worked_example_records_both_control_states,
        _drop_the_fixed_state_from_the_worked_example,
    ),
    (
        check_the_unverified_claims_name_their_settling_experiment,
        _strip_the_settling_experiments,
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


def test_the_half_control_mutant_is_schema_legal() -> None:
    """A control asserted only in the broken state is valid DSL and proves nothing."""
    broken = K.mutant(DOC, _accept_a_control_that_only_fired_once)
    assert K.schema_errors(broken) == []
    assert K.semantic_violations(broken) == []
    assert K.raises_assertion(
        check_the_control_requires_different_outcomes_in_both_states, broken
    )
