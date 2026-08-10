"""FLAGSHIP end-to-end test for `firing-path-revalidation` (bp-8, slot 93, BP-MNT-02).

Mechanism claims under test: a verdict must come from an OBSERVED trigger, never from reading
configuration (a hook registered in a manifest is not a hook that fires); a component that cannot
be triggered is UNKNOWN, never assumed healthy; the run is worthless without a DELTA against the
previous scorecard, so ``previous_scorecard`` is a required param and the delta gate is blocking -
a single scorecard cannot tell you anything was lost; a shrinking inventory is a disappearance, not
a clean run; and the workflow is forbidden from writing to the hooks and settings it measures,
because an instrument that can edit its subject is not an instrument.

Every check ships with a targeted mutant and is asserted to FAIL on it.
"""

from __future__ import annotations

from typing import Any, Mapping

import bp8_testkit as K
import pytest

WORKFLOW_ID = "firing-path-revalidation"
DOC = K.load(WORKFLOW_ID)


# ------------------------------------------------------------------------------- the checks


def check_a_verdict_may_not_come_from_configuration(doc: Mapping[str, Any]) -> None:
    spec = K.gate_for_stage(doc, "gate-no-config-verdicts")
    assert "verdicts_from_config_only == 0" in spec["expression"], (
        "a registration entry is not evidence that a path fires"
    )
    assert "unknown_declared_where_untriggerable == true" in spec["expression"], (
        "an untriggerable component must be UNKNOWN, not folded into healthy"
    )
    assert spec["blocking"] is True and spec["on_fail"] == "fail"


def check_the_trigger_is_active_not_a_config_read(doc: Mapping[str, Any]) -> None:
    fan = K.fanout(doc, "probe-components")
    assert fan["over"]["ref"] == "expected_firing_evidence"
    body_ids = [str(st["id"]) for st in fan["body"]]
    assert body_ids == ["trigger-and-observe"], f"the probe body changed shape: {body_ids}"
    spec = doc["params"]["expected_firing_evidence"]
    props = spec["items"]["properties"]
    for field in ("trigger", "evidence_path", "evidence_marker"):
        assert field in props, f"a probe with no {field!r} cannot observe anything"
    assert spec["min_items"] >= 1


def check_the_delta_is_mandatory_not_optional(doc: Mapping[str, Any]) -> None:
    assert doc["params"]["previous_scorecard"].get("required") is True, (
        "without a previous scorecard this degenerates into the snapshot it exists to replace"
    )
    spec = K.gate_for_stage(doc, "gate-delta")
    assert "previous_scorecard_loaded == true" in spec["expression"]
    assert "delta_rows == current_rows" in spec["expression"], (
        "a delta covering fewer rows than the scorecard hides the rows it omitted"
    )
    assert spec["blocking"] is True and spec["on_fail"] == "fail"
    assert "previous-scorecard-missing" in doc["retry_policy"]["no_retry_on"]


def check_the_delta_stage_runs_after_classification(doc: Mapping[str, Any]) -> None:
    order = K.top_level_stage_ids(doc)
    K.assert_precedes(order, "probe-components", "classify-firing")
    K.assert_precedes(order, "classify-firing", "gate-no-config-verdicts")
    K.assert_precedes(order, "gate-no-config-verdicts", "diff-against-previous")
    assert K.depends_on(doc, "diff-against-previous") == ["gate-no-config-verdicts"], (
        "the diff must be reachable only through the no-config-verdicts gate"
    )


def check_a_shrinking_inventory_is_not_a_clean_run(doc: Mapping[str, Any]) -> None:
    spec = K.gate_for_stage(doc, "gate-inventory")
    assert "inventory_component_count >= previous_component_count" in spec["expression"], (
        "a component that vanished from the inventory would otherwise read as zero findings"
    )
    assert "inventory_age_seconds <=" in spec["expression"], (
        "a stale inventory silently narrows the population"
    )
    assert spec["on_fail"] == "escalate-to-human"
    assert "component-disappeared" in doc["failure_policy"]["classify_as"]


def check_the_five_state_vocabulary_is_enforced_by_failure_classes(doc: Mapping[str, Any]) -> None:
    no_retry = set(doc["retry_policy"]["no_retry_on"])
    assert "inert-misread-as-firing" in no_retry, (
        "WIRED-BUT-INERT must be a distinct state from FIRES, and misreading it is not a flake"
    )
    assert "unknown-folded-into-healthy" in no_retry
    assert "unknown-folded-into-healthy" in doc["failure_policy"]["classify_as"]
    ids = {c["id"] for c in K.benchmark_cases(doc)}
    assert "cold-feed-is-inert" in ids, "the INERT state needs a case or it is decoration"
    assert "deliberate-disarm" in ids, "the DISARMED state needs its both-states control"


def check_the_identity_case_proves_the_differ(doc: Mapping[str, Any]) -> None:
    cases = {c["id"]: c for c in K.benchmark_cases(doc)}
    assert "identical-scorecards" in cases, (
        "a differ that reports regressions on identical input is broken, and only this case sees it"
    )
    assert "zero regressions" in cases["identical-scorecards"]["expect"]


def check_a_regression_escalates_and_never_completes(doc: Mapping[str, Any]) -> None:
    rule = K.stopping_rule(doc, "regression-found")
    assert "regressions > 0" in rule["expression"]
    assert rule["on_stop"] == "escalate"
    complete = K.stopping_rule(doc, "scorecard-and-delta-complete")
    assert "previous_scorecard_loaded == true" in complete["minimum_conditions"], (
        "completion must be conditioned on the delta, not merely preceded by it"
    )


def check_the_shared_budget_breach_is_visible(doc: Mapping[str, Any]) -> None:
    rule = K.stopping_rule(doc, "budget-breach-visible")
    assert "shared_budget_cost_ms >= shared_budget_ceiling_ms" in rule["expression"]
    assert rule["on_stop"] == "escalate"
    ceiling = doc["params"]["shared_budget_ceiling_ms"]
    assert ceiling["minimum"] >= 1 and ceiling["default"] > 0, (
        "a zero or absent ceiling makes the breach rule unfireable"
    )
    assert "budget-ceiling-breached" in doc["failure_policy"]["classify_as"]


def check_the_instrument_cannot_edit_its_subject(doc: Mapping[str, Any]) -> None:
    policy = doc["tool_policy"]
    assert policy["default"] == "deny"
    assert policy["network"] == "none"
    forbidden = set(policy["forbid_write_paths"])
    assert ".claude/hooks/**" in forbidden
    assert ".claude/settings.json" in forbidden
    assert policy["write_paths"] == ["command-center/firing/**"]


def check_the_probe_barrier_degrades_loudly(doc: Mapping[str, Any]) -> None:
    spec = K.barrier(doc, "probe-components")
    K.assert_rejects_fire_and_forget(spec)
    assert spec["mode"] == "quorum" and 0 < spec["quorum"] <= 1
    assert spec["on_partial"] == "proceed-degraded"
    assert doc["failure_policy"]["on_failure"] == "degrade-loudly", (
        "a partially probed census must announce its partiality, not smooth it over"
    )
    assert doc["failure_policy"]["never_silent"] is True


def check_a_firing_verdict_is_never_served_from_cache(doc: Mapping[str, Any]) -> None:
    assert doc["cache"]["enabled"] is False, (
        "a cached firing verdict is a snapshot of the past presented as the present"
    )
    forbidden = set(doc["dry_run"]["forbid_tools"])
    assert "Bash:python" in forbidden, "a dry run must not actually trigger anything"
    assert doc["dry_run"]["side_effect_free"] is True


def check_the_worked_example_shows_a_stable_but_unhealthy_row(doc: Mapping[str, Any]) -> None:
    example = K.worked_examples(doc)[0]
    verdicts = {row["component"]: row["verdict"] for row in example["delta"]}
    assert "REGRESSION" in verdicts.values(), "the example must show the delta earning its keep"
    assert any(v.startswith("stable-but-unhealthy") for v in verdicts.values()), (
        "the INERT-and-stable row is the case a delta-only alarm misses; it must be in the example"
    )
    states = {row["fires"] for row in example["scorecard"]}
    assert len(states) >= 3, (
        "a worked example showing one or two states cannot demonstrate a five-state classification"
    )
    assert example["disarmed_count"]["current"] != example["disarmed_count"]["previous"]


ALL_CHECKS = (
    check_a_verdict_may_not_come_from_configuration,
    check_the_trigger_is_active_not_a_config_read,
    check_the_delta_is_mandatory_not_optional,
    check_the_delta_stage_runs_after_classification,
    check_a_shrinking_inventory_is_not_a_clean_run,
    check_the_five_state_vocabulary_is_enforced_by_failure_classes,
    check_the_identity_case_proves_the_differ,
    check_a_regression_escalates_and_never_completes,
    check_the_shared_budget_breach_is_visible,
    check_the_instrument_cannot_edit_its_subject,
    check_the_probe_barrier_degrades_loudly,
    check_a_firing_verdict_is_never_served_from_cache,
    check_the_worked_example_shows_a_stable_but_unhealthy_row,
)


@pytest.mark.parametrize("check", ALL_CHECKS, ids=lambda c: c.__name__)
def test_shipped_blueprint_satisfies_every_mechanism_check(check: Any) -> None:
    check(DOC)


def test_shipped_blueprint_is_conformant() -> None:
    assert K.schema_errors(DOC) == []
    assert K.semantic_violations(DOC) == []
    assert K.blueprint_meta(DOC)["slot"] == 93
    assert K.blueprint_meta(DOC)["design_card"] == "BP-MNT-02"
    assert DOC["flagship"] is True


# ------------------------------------------------------------------------- mutation controls


def _accept_a_config_only_verdict(doc: dict) -> None:
    doc["gates"]["no-config-only-verdicts"]["expression"] = "components_classified > 0"


def _drop_the_evidence_marker_from_a_probe(doc: dict) -> None:
    doc["params"]["expected_firing_evidence"]["items"]["properties"].pop("evidence_marker")


def _make_the_previous_scorecard_optional(doc: dict) -> None:
    doc["params"]["previous_scorecard"].pop("required")


def _diff_before_the_classification_gate(doc: dict) -> None:
    K.find_stage_mut(doc, "diff-against-previous")["depends_on"] = ["classify-firing"]


def _accept_a_shrinking_inventory(doc: dict) -> None:
    doc["gates"]["inventory-is-current"]["expression"] = "inventory_age_seconds <= 604800"


def _retry_an_inert_misread(doc: dict) -> None:
    doc["retry_policy"]["no_retry_on"] = ["previous-scorecard-missing"]


def _drop_the_identity_case(doc: dict) -> None:
    doc["x_extensions"]["benchmark_cases"] = [
        c for c in doc["x_extensions"]["benchmark_cases"] if c["id"] != "identical-scorecards"
    ]


def _let_a_regression_complete(doc: dict) -> None:
    for rule in doc["stopping_rules"]:
        if rule["id"] == "regression-found":
            rule["on_stop"] = "complete"


def _zero_the_budget_ceiling(doc: dict) -> None:
    doc["params"]["shared_budget_ceiling_ms"]["default"] = 0


def _allow_writes_into_the_hooks_tree(doc: dict) -> None:
    doc["tool_policy"]["forbid_write_paths"] = ["platform/schema/**"]


def _hide_the_partial_probe(doc: dict) -> None:
    doc["failure_policy"]["on_failure"] = "fail-fast"
    doc["failure_policy"]["never_silent"] = False


def _enable_the_cache(doc: dict) -> None:
    doc["cache"]["enabled"] = True


def _collapse_the_worked_example_to_a_binary(doc: dict) -> None:
    for row in doc["x_extensions"]["worked_examples"][0]["scorecard"]:
        row["fires"] = "FIRES"


MUTATIONS = (
    (check_a_verdict_may_not_come_from_configuration, _accept_a_config_only_verdict),
    (check_the_trigger_is_active_not_a_config_read, _drop_the_evidence_marker_from_a_probe),
    (check_the_delta_is_mandatory_not_optional, _make_the_previous_scorecard_optional),
    (check_the_delta_stage_runs_after_classification, _diff_before_the_classification_gate),
    (check_a_shrinking_inventory_is_not_a_clean_run, _accept_a_shrinking_inventory),
    (check_the_five_state_vocabulary_is_enforced_by_failure_classes, _retry_an_inert_misread),
    (check_the_identity_case_proves_the_differ, _drop_the_identity_case),
    (check_a_regression_escalates_and_never_completes, _let_a_regression_complete),
    (check_the_shared_budget_breach_is_visible, _zero_the_budget_ceiling),
    (check_the_instrument_cannot_edit_its_subject, _allow_writes_into_the_hooks_tree),
    (check_the_probe_barrier_degrades_loudly, _hide_the_partial_probe),
    (check_a_firing_verdict_is_never_served_from_cache, _enable_the_cache),
    (check_the_worked_example_shows_a_stable_but_unhealthy_row, _collapse_the_worked_example_to_a_binary),
)


@pytest.mark.parametrize("check,mutate", MUTATIONS, ids=lambda v: getattr(v, "__name__", ""))
def test_each_check_fails_on_its_mutated_blueprint(check: Any, mutate: Any) -> None:
    broken = K.mutant(DOC, mutate)
    assert K.raises_assertion(check, broken), (
        f"{check.__name__} stayed silent on the mutated blueprint, so it measures nothing"
    )


def test_the_config_only_verdict_mutant_is_schema_legal() -> None:
    """The snapshot-from-configuration defect: valid DSL, and only this suite rejects it."""
    broken = K.mutant(DOC, _accept_a_config_only_verdict)
    assert K.schema_errors(broken) == []
    assert K.semantic_violations(broken) == []
    assert K.raises_assertion(check_a_verdict_may_not_come_from_configuration, broken)
