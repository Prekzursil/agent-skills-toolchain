"""FLAGSHIP end-to-end test for `silent-disarm-hunt` (bp-4, doc-order 48, BP-DBG-05).

Mechanism claims under test: a FOUR-way cross-check (handler on disk -> registration in every
channel -> event name against the generator's tuple -> observed fire); LIVE requires an observed
fire, never mere registration; the reachability scan has its own detector control (it must find
the two handlers already known to be unreachable); fail-open AST hits are CANDIDATES that get a
both-states probe rather than a verdict; and the whole sweep is read-only, which is why it is the
only blueprint in this range with no human checkpoint.
"""

from __future__ import annotations

from typing import Any, Mapping

import bp4_testkit as K
import pytest

WORKFLOW_ID = "silent-disarm-hunt"
DOC = K.load(WORKFLOW_ID)


# ------------------------------------------------------------------------------- the checks


def check_the_four_way_cross_check_is_present_and_ordered(
    doc: Mapping[str, Any],
) -> None:
    order = K.top_level_stage_ids(doc)
    for earlier, later in (
        ("enumerate-handlers", "enumerate-registrations"),
        ("enumerate-registrations", "check-event-reachability"),
        ("check-event-reachability", "scan-fail-open-paths"),
        ("scan-fail-open-paths", "probe-suspects"),
        ("probe-suspects", "classify-handlers"),
    ):
        K.assert_precedes(order, earlier, later)
    assert "event_generator_source" in doc["params"], (
        "the generator that PRODUCES the registrations is the fourth axis; without it the check is three-way"
    )


def check_live_requires_an_observed_fire(doc: Mapping[str, Any]) -> None:
    gate = K.gate(doc, "live-requires-observed-fire")
    assert "handlers_marked_live_without_observed_fire == 0" in gate["expression"]
    assert "handlers_unclassified == 0" in gate["expression"]
    assert gate["blocking"] is True and gate["on_fail"] == "fail"
    assert "observed_fire_window_hours" in doc["params"]


def check_every_registration_channel_is_read(doc: Mapping[str, Any]) -> None:
    gate = K.gate(doc, "all-channels-read")
    assert "channels_read == channels_declared" in gate["expression"]
    assert "channels_declared >= 2" in gate["expression"], (
        "a single-channel sweep cannot see a handler registered in one place and not another"
    )
    fanout = K.stage(doc, "enumerate-registrations")
    assert fanout["over"]["source"] == "param"
    assert fanout["over"]["ref"] == "registration_channels"
    assert fanout["on_item_failure"] == "abort", (
        "an unread channel must stop the sweep, not be skipped"
    )


def check_the_scan_has_its_own_detector_control(doc: Mapping[str, Any]) -> None:
    gate = K.gate(doc, "known-unreachable-found")
    assert "known_unreachable_handlers_found >= 2" in gate["expression"], (
        "the two handlers already known unreachable are the scan's known-present control"
    )
    assert "scan_detector_validated == true" in gate["expression"]
    assert gate["blocking"] is True and gate["on_fail"] == "fail"


def check_fail_open_hits_are_candidates_not_verdicts(doc: Mapping[str, Any]) -> None:
    stage = K.stage(doc, "scan-fail-open-paths")
    paths = {a["path"] for a in stage["produces"]}
    assert any("candidates" in p for p in paths), (
        "the AST pass emits CANDIDATES - its heuristics have false positives"
    )
    probe = K.stage(doc, "both-states-on-suspect")
    assert probe["kind"] == "subworkflow"
    assert probe["workflow"]["workflow_id"] == "both-states-detector-control"
    assert K.stage(doc, "probe-suspects")["over"]["source"] == "artifact"


def check_silence_is_not_treated_as_a_pass(doc: Mapping[str, Any]) -> None:
    gate = K.gate(doc, "no-findings-is-not-evidence")
    assert "silence_treated_as_pass == false" in gate["expression"]
    assert "disarmed_aggregate_line_read == true" in gate["expression"], (
        "the dispatcher's own DISARMED aggregate is a first-class input, not something to recompute"
    )
    assert gate["blocking"] is True


def check_the_sweep_is_read_only(doc: Mapping[str, Any]) -> None:
    policy = doc["tool_policy"]
    assert {"Edit", "Write"} <= set(policy["deny"]), (
        "a sweep that can edit is not an audit"
    )
    forbidden = set(policy["forbid_write_paths"])
    assert {"hooks/**", ".claude/**"} <= forbidden
    assert doc["estimate"]["impact"]["risk"] == "low"


def check_it_has_no_human_checkpoint(doc: Mapping[str, Any]) -> None:
    """It changes nothing, so there is nothing to approve - the distinctness marker of this one."""
    kinds = {st.get("kind") for _, st in K.stages(doc)}
    assert "human_checkpoint" not in kinds
    assert "escalate_to" not in doc["failure_policy"], (
        "with no checkpoint there is no in-workflow escalation target to name"
    )


def check_live_and_repo_trees_are_diffed(doc: Mapping[str, Any]) -> None:
    stage = K.stage(doc, "live-vs-repo-diff")
    assert stage.get("when") == "compare_live_to_repo == true"
    paths = {a["path"] for a in stage["produces"]}
    assert "command-center/disarm/live-repo-drift.json" in paths, (
        "a deployed-copy edit is invisible to git and dies on the next deploy - it must be recorded"
    )
    assert "live-repo-drift" in doc["outputs"]


def check_classification_vocabulary_is_closed(doc: Mapping[str, Any]) -> None:
    output = DOC["x_extensions"]["worked_example"]["s5_outcome"]
    for token in ("UNREACHABLE", "DISARMED", "LIVE", "UNKNOWN"):
        assert token in output, f"the worked example does not exercise {token}"
    assert "unreachable-handler" in doc["failure_policy"]["classify_as"]
    assert "fail-open-path" in doc["failure_policy"]["classify_as"]


ALL_CHECKS = (
    check_the_four_way_cross_check_is_present_and_ordered,
    check_live_requires_an_observed_fire,
    check_every_registration_channel_is_read,
    check_the_scan_has_its_own_detector_control,
    check_fail_open_hits_are_candidates_not_verdicts,
    check_silence_is_not_treated_as_a_pass,
    check_the_sweep_is_read_only,
    check_it_has_no_human_checkpoint,
    check_live_and_repo_trees_are_diffed,
    check_classification_vocabulary_is_closed,
)


@pytest.mark.parametrize("check", ALL_CHECKS, ids=lambda c: c.__name__)
def test_shipped_blueprint_satisfies_every_mechanism_check(check: Any) -> None:
    check(DOC)


def test_shipped_blueprint_is_conformant() -> None:
    assert K.schema_errors(DOC) == []
    assert K.semantic_violations(DOC) == []


# ------------------------------------------------------------------------- mutation controls


def _remove_the_generator_axis(doc: dict) -> None:
    doc["params"].pop("event_generator_source")


def _let_registration_imply_live(doc: dict) -> None:
    doc["gates"]["live-requires-observed-fire"]["expression"] = (
        "handlers_registered >= 1"
    )


def _read_a_single_channel(doc: dict) -> None:
    doc["gates"]["all-channels-read"]["expression"] = "channels_read >= 1"
    K.find_stage_mut(doc, "enumerate-registrations")["on_item_failure"] = "continue"


def _drop_the_scan_control(doc: dict) -> None:
    doc["gates"]["known-unreachable-found"]["expression"] = "scan_completed == true"


def _treat_ast_hits_as_verdicts(doc: dict) -> None:
    stage = K.find_stage_mut(doc, "probe-suspects")
    stage["body"] = [
        {
            "id": "both-states-on-suspect",
            "title": "Accept the AST finding as the verdict",
            "kind": "task",
            "role": "classifier",
            "work_unit_ref": "AUD-0045",
        }
    ]


def _accept_silence_as_a_pass(doc: dict) -> None:
    doc["gates"]["no-findings-is-not-evidence"]["expression"] = "scan_ran == true"


def _grant_write_access(doc: dict) -> None:
    doc["tool_policy"]["deny"] = ["WebFetch", "WebSearch"]


def _add_a_human_checkpoint(doc: dict) -> None:
    doc["stages"].append(
        {
            "id": "owner-wire-or-retire",
            "title": "Ask the owner to wire or retire the unreachable handlers",
            "kind": "human_checkpoint",
            "depends_on": ["silence-gate"],
            "prompt": "Wire the unreachable handlers or retire them?",
            "approvers": ["owner"],
            "approval_mode": "owner-only",
            "timeout_seconds": 86400,
            "on_timeout": "escalate",
            "options": ["wire", "retire"],
        }
    )


def _drop_the_live_repo_diff(doc: dict) -> None:
    fanout = K.find_stage_mut(doc, "enumerate-registrations")
    fanout["body"] = [st for st in fanout["body"] if st["id"] != "live-vs-repo-diff"]


def _narrow_the_classification_vocabulary(doc: dict) -> None:
    doc["failure_policy"]["classify_as"] = ["detector-truncation"]


MUTATIONS = (
    (check_the_four_way_cross_check_is_present_and_ordered, _remove_the_generator_axis),
    (check_live_requires_an_observed_fire, _let_registration_imply_live),
    (check_every_registration_channel_is_read, _read_a_single_channel),
    (check_the_scan_has_its_own_detector_control, _drop_the_scan_control),
    (check_fail_open_hits_are_candidates_not_verdicts, _treat_ast_hits_as_verdicts),
    (check_silence_is_not_treated_as_a_pass, _accept_silence_as_a_pass),
    (check_the_sweep_is_read_only, _grant_write_access),
    (check_it_has_no_human_checkpoint, _add_a_human_checkpoint),
    (check_live_and_repo_trees_are_diffed, _drop_the_live_repo_diff),
    (check_classification_vocabulary_is_closed, _narrow_the_classification_vocabulary),
)


@pytest.mark.parametrize(
    "check,mutate", MUTATIONS, ids=lambda v: getattr(v, "__name__", "")
)
def test_each_check_fails_on_its_mutated_blueprint(check: Any, mutate: Any) -> None:
    broken = K.mutant(DOC, mutate)
    assert K.raises_assertion(check, broken), (
        f"{check.__name__} stayed silent on the mutated blueprint, so it measures nothing"
    )


def test_registration_implies_live_mutant_is_schema_legal() -> None:
    """The whole failure class lives in valid DSL - a schema cannot see 'registered != live'."""
    broken = K.mutant(DOC, _let_registration_imply_live)
    assert K.schema_errors(broken) == []
    assert K.semantic_violations(broken) == []
    assert K.raises_assertion(check_live_requires_an_observed_fire, broken)
