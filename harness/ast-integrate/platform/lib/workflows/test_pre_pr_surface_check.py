"""FLAGSHIP end-to-end test for `pre-pr-surface-check` (bp-8, slot 88, design BP-REL-02).

Mechanism claims under test: the surface is measured COMMIT-TO-COMMIT with three dots, so
working-tree noise cannot be folded into what the PR proposes (a two-dot read is how untracked
credential files appear to be "in the PR" when they are not); the base must be freshly resolved,
because a stale base makes the measurement a confident lie; the untracked enumeration must be
listed BY NAME (proving an all-untracked walk ran) and never by content; and there is NO MODEL in
the measurement path at all - which is why the document declares no ``model_routing`` and refuses
to cache a verdict, since a cached surface certifies a branch tip that has since moved.

Every check ships with a targeted mutant and is asserted to FAIL on it.
"""

from __future__ import annotations

from typing import Any, Mapping

import bp8_testkit as K
import pytest

WORKFLOW_ID = "pre-pr-surface-check"
DOC = K.load(WORKFLOW_ID)


# ------------------------------------------------------------------------------- the checks


def check_three_dots_only_and_no_working_tree_noise(doc: Mapping[str, Any]) -> None:
    spec = K.gate_for_stage(doc, "gate-three-dot")
    assert "diff_mode == THREE_DOT" in spec["expression"]
    assert "working_tree_noise_folded_in == false" in spec["expression"], (
        "plain `git diff origin/main` folds in the working tree; that is the measured defect"
    )
    assert spec["blocking"] is True and spec["on_fail"] == "fail"


def check_the_base_must_be_freshly_resolved(doc: Mapping[str, Any]) -> None:
    spec = K.gate_for_stage(doc, "gate-base")
    assert "base_resolved == true" in spec["expression"]
    assert "base_fetch_age_seconds <=" in spec["expression"], (
        "a surface measured against an unfetched base understates what the PR deletes"
    )
    assert spec["blocking"] is True and spec["on_fail"] == "fail"
    rule = K.stopping_rule(doc, "base-unresolvable")
    assert rule["on_stop"] == "escalate", "an unresolvable base is not a clean surface"


def check_the_gates_precede_every_classification(doc: Mapping[str, Any]) -> None:
    order = K.top_level_stage_ids(doc)
    K.assert_precedes(order, "gate-base", "gate-three-dot")
    K.assert_precedes(order, "gate-three-dot", "classify-deletions")
    K.assert_precedes(order, "gate-three-dot", "list-untracked-noise")
    assert K.depends_on(doc, "classify-deletions") == ["gate-three-dot"]
    assert K.depends_on(doc, "list-untracked-noise") == ["gate-three-dot"]


def check_the_verdict_needs_both_halves_of_the_surface(doc: Mapping[str, Any]) -> None:
    deps = set(K.depends_on(doc, "emit-verdict"))
    assert deps == {"classify-deletions", "list-untracked-noise"}, (
        "a verdict emitted without the untracked enumeration reports a partial surface as total"
    )
    K.assert_precedes(K.top_level_stage_ids(doc), "emit-verdict", "gate-verdict")


def check_untracked_credentials_are_named_by_pattern(doc: Mapping[str, Any]) -> None:
    spec = doc["params"]["credential_name_patterns"]
    assert spec["min_items"] >= 1, "an empty pattern list makes the enumeration vacuous"
    defaults = set(spec["default"])
    for needed in ("*.pem", "*.key", ".env*"):
        assert needed in defaults, f"the default credential patterns omit {needed!r}"
    ids = {c["id"] for c in K.benchmark_cases(doc)}
    assert "untracked-dir-credential" in ids, (
        "the collapsed-untracked-directory case is the reason -uall is load-bearing"
    )


def check_the_deletion_verdict_cannot_pass_silently(doc: Mapping[str, Any]) -> None:
    spec = K.gate_for_stage(doc, "gate-verdict")
    assert "cherry_pick_alternative_proposed == true" in spec["expression"], (
        "a STOP verdict must arrive with an alternative, not just a refusal"
    )
    assert spec["on_fail"] == "escalate-to-human"
    ratio = doc["params"]["deletion_ratio_stop"]
    assert ratio["type"] == "number" and 0 <= ratio["default"] <= 1


def check_there_is_no_model_in_the_measurement_path(doc: Mapping[str, Any]) -> None:
    assert "model_routing" not in doc, (
        "declaring a model router here would imply a judgement step inside a deterministic measurement"
    )
    for name, role in doc["roles"].items():
        if role.get("vendor") == "human":
            continue
        assert "model" not in role, (
            f"role {name!r} pins a model inside the measurement path"
        )


def check_the_surface_is_never_served_from_cache(doc: Mapping[str, Any]) -> None:
    assert doc["cache"]["enabled"] is False, (
        "a cached surface measurement certifies a stale branch tip"
    )
    assert doc["resume"]["enabled"] is False, (
        "resuming a surface measurement mixes two branch states into one verdict"
    )
    assert doc["retry_policy"]["strategy"] == "none"
    assert "base-unresolvable" in doc["retry_policy"]["no_retry_on"]


def check_the_measurement_is_byte_reproducible(doc: Mapping[str, Any]) -> None:
    replay = doc["replay"]
    assert replay["deterministic"] is True
    assert replay["verify"] == "hash-equal"
    assert replay["on_divergence"] == "fail"
    forbidden = set(replay["forbid_nondeterministic_sources"])
    assert {"clock", "random", "filesystem-order"} <= forbidden, (
        "filesystem order is the one that silently reorders an untracked enumeration"
    )


def check_the_workflow_cannot_mutate_the_repo_it_measures(
    doc: Mapping[str, Any],
) -> None:
    policy = doc["tool_policy"]
    assert policy["default"] == "deny"
    assert policy["network"] == "none"
    assert "Bash" in policy["deny"]
    assert ".git/**" in policy["forbid_write_paths"], (
        "a measurement that can write .git can change the thing it is measuring"
    )
    assert policy["write_paths"] == ["command-center/release/**"]


def check_the_verdict_is_a_typed_artifact_for_the_shepherd(
    doc: Mapping[str, Any],
) -> None:
    out = doc["outputs"]["verdict"]
    assert out["sentinel"].startswith("SUCCESS:"), "a terminal-state marker is required"
    assert "pr-shepherd-to-merge" in out["consumers"], (
        "the dependency runs one way: this feeds the shepherd, never the reverse"
    )
    resolved = K.resolve_schema_reference(out["schema_ref"])
    assert resolved is not None and resolved.is_file(), (
        f"the declared output schema does not exist on disk: {out['schema_ref']}"
    )
    assert out["min_bytes"] >= 1, (
        "an empty artifact must not satisfy the output contract"
    )


def check_the_worked_example_carries_the_recorded_numbers(
    doc: Mapping[str, Any],
) -> None:
    example = K.worked_examples(doc)[0]
    measured = example["measured_surface"]
    assert measured["diff_mode"] == "THREE_DOT"
    assert measured["deletions"] > measured["insertions"], (
        "the worked example must be the stale-branch shape it exists to illustrate"
    )
    assert example["verdict"] == "STOP"
    alt = example["alternative_surface"]
    assert alt["deletions"] < measured["deletions"], (
        "the proposed alternative must actually reduce the surface"
    )
    assert (
        measured["deletion_ratio"] > doc["params"]["deletion_ratio_stop"]["default"]
    ), (
        "the example would not trip the shipped default threshold, so it proves nothing about it"
    )


ALL_CHECKS = (
    check_three_dots_only_and_no_working_tree_noise,
    check_the_base_must_be_freshly_resolved,
    check_the_gates_precede_every_classification,
    check_the_verdict_needs_both_halves_of_the_surface,
    check_untracked_credentials_are_named_by_pattern,
    check_the_deletion_verdict_cannot_pass_silently,
    check_there_is_no_model_in_the_measurement_path,
    check_the_surface_is_never_served_from_cache,
    check_the_measurement_is_byte_reproducible,
    check_the_workflow_cannot_mutate_the_repo_it_measures,
    check_the_verdict_is_a_typed_artifact_for_the_shepherd,
    check_the_worked_example_carries_the_recorded_numbers,
)


@pytest.mark.parametrize("check", ALL_CHECKS, ids=lambda c: c.__name__)
def test_shipped_blueprint_satisfies_every_mechanism_check(check: Any) -> None:
    check(DOC)


def test_shipped_blueprint_is_conformant() -> None:
    assert K.schema_errors(DOC) == []
    assert K.semantic_violations(DOC) == []
    assert K.blueprint_meta(DOC)["slot"] == 88
    assert K.blueprint_meta(DOC)["design_card"] == "BP-REL-02"
    assert DOC["flagship"] is True


# ------------------------------------------------------------------------- mutation controls


def _allow_a_two_dot_surface(doc: dict) -> None:
    doc["gates"]["three-dot-only"]["expression"] = "diff_mode == THREE_DOT"


def _drop_the_base_freshness_bound(doc: dict) -> None:
    doc["gates"]["base-is-resolvable"]["expression"] = "base_resolved == true"


def _classify_before_the_three_dot_gate(doc: dict) -> None:
    K.find_stage_mut(doc, "classify-deletions")["depends_on"] = ["gate-base"]


def _emit_the_verdict_without_the_untracked_walk(doc: dict) -> None:
    K.find_stage_mut(doc, "emit-verdict")["depends_on"] = ["classify-deletions"]


def _empty_the_credential_patterns(doc: dict) -> None:
    doc["params"]["credential_name_patterns"]["default"] = ["*.pem"]


def _let_the_verdict_stand_without_an_alternative(doc: dict) -> None:
    doc["gates"]["deletion-ratio-verdict"]["expression"] = (
        "verdict == SAFE OR verdict == REVIEW"
    )


def _add_a_model_router(doc: dict) -> None:
    doc["model_routing"] = {
        "strategy": "static",
        "default": {"model": "opus", "vendor": "anthropic", "effort": "high"},
    }


def _enable_the_cache(doc: dict) -> None:
    doc["cache"]["enabled"] = True


def _allow_filesystem_order_nondeterminism(doc: dict) -> None:
    replay = doc["replay"]
    replay["forbid_nondeterministic_sources"] = ["clock", "random", "network"]


def _allow_writes_into_dot_git(doc: dict) -> None:
    doc["tool_policy"]["forbid_write_paths"] = ["command-center/WORK-UNIT-CATALOG.json"]


def _drop_the_output_sentinel(doc: dict) -> None:
    doc["outputs"]["verdict"]["sentinel"] = "done"


def _flatten_the_worked_example_surface(doc: dict) -> None:
    doc["x_extensions"]["worked_examples"][0]["measured_surface"]["deletion_ratio"] = (
        0.01
    )


MUTATIONS = (
    (check_three_dots_only_and_no_working_tree_noise, _allow_a_two_dot_surface),
    (check_the_base_must_be_freshly_resolved, _drop_the_base_freshness_bound),
    (check_the_gates_precede_every_classification, _classify_before_the_three_dot_gate),
    (
        check_the_verdict_needs_both_halves_of_the_surface,
        _emit_the_verdict_without_the_untracked_walk,
    ),
    (check_untracked_credentials_are_named_by_pattern, _empty_the_credential_patterns),
    (
        check_the_deletion_verdict_cannot_pass_silently,
        _let_the_verdict_stand_without_an_alternative,
    ),
    (check_there_is_no_model_in_the_measurement_path, _add_a_model_router),
    (check_the_surface_is_never_served_from_cache, _enable_the_cache),
    (
        check_the_measurement_is_byte_reproducible,
        _allow_filesystem_order_nondeterminism,
    ),
    (check_the_workflow_cannot_mutate_the_repo_it_measures, _allow_writes_into_dot_git),
    (check_the_verdict_is_a_typed_artifact_for_the_shepherd, _drop_the_output_sentinel),
    (
        check_the_worked_example_carries_the_recorded_numbers,
        _flatten_the_worked_example_surface,
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


def test_the_two_dot_mutant_is_schema_legal() -> None:
    """The defect's exact shape: a two-dot surface is perfectly valid DSL and silently wrong."""
    broken = K.mutant(DOC, _allow_a_two_dot_surface)
    assert K.schema_errors(broken) == []
    assert K.semantic_violations(broken) == []
    assert K.raises_assertion(check_three_dots_only_and_no_working_tree_noise, broken)
