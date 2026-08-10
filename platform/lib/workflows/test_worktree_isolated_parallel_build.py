"""FLAGSHIP end-to-end test for `worktree-isolated-parallel-build` (bp-4, doc-order 39, BP-IMP-02).

Mechanism claims under test: worktrees are PRE-CREATED before any unit runs; each branch is cut
from an EXPLICIT base_ref rather than a moving HEAD; the empty-index staged-deletions trap is
gated before any commit; a broad `git add -A` is denied by policy; integration is serial behind a
hard barrier; and a unit that cannot get a tree is downgraded WITH a written record.
"""

from __future__ import annotations

from typing import Any, Mapping

import bp4_testkit as K
import pytest

WORKFLOW_ID = "worktree-isolated-parallel-build"
DOC = K.load(WORKFLOW_ID)


# ------------------------------------------------------------------------------- the checks


def check_worktrees_are_pre_created_before_any_unit_runs(
    doc: Mapping[str, Any],
) -> None:
    K.assert_precedes(K.top_level_stage_ids(doc), "pre-create-worktrees", "run-units")
    run_units = K.stage(doc, "run-units")
    # the fan-out iterates the manifest the pre-create stage produced, so it cannot start first
    assert run_units["over"]["source"] == "artifact"
    assert run_units["over"]["ref"] == "command-center/isolation/worktree-manifest.json"
    produced = {
        artifact["path"]
        for artifact in K.stage(doc, "pre-create-worktrees").get("produces", [])
    }
    assert run_units["over"]["ref"] in produced, (
        "the fan-out must consume the manifest that pre-creation writes, or creation can race"
    )


def check_branches_are_cut_from_an_explicit_base_ref(doc: Mapping[str, Any]) -> None:
    base = doc["params"].get("base_ref")
    assert base is not None, "base_ref must be a declared parameter"
    assert base.get("default") == "origin/main"
    assert "HEAD" not in str(base.get("default")), "HEAD drifts while the fan-out runs"
    unit = K.stage(doc, "pre-create-worktrees")["work_unit"]
    assert (
        "base_ref" in unit["question_or_target"]
        and "never HEAD" in unit["question_or_target"]
    )
    assert "params.base_ref" in unit["inputs"]


def check_empty_index_trap_is_gated_before_commit(doc: Mapping[str, Any]) -> None:
    gate = K.gate(doc, "empty-index-guard")
    assert gate["blocking"] is True
    assert "staged_deletions == 0" in gate["expression"]
    K.assert_precedes(
        K.top_level_stage_ids(doc), "empty-index-gate", "integrate-serially"
    )


def check_broad_add_is_denied_by_policy_and_by_gate(doc: Mapping[str, Any]) -> None:
    assert "Bash:git-add-all" in doc["tool_policy"]["deny"]
    gate = K.gate(doc, "no-broad-add")
    assert gate["blocking"] is True
    assert "broad_add_all_invocations == 0" in gate["expression"]
    assert "every_add_is_path_scoped == true" in gate["expression"]


def check_integration_is_serial_behind_a_hard_barrier(doc: Mapping[str, Any]) -> None:
    barrier = K.stage(doc, "integration-barrier")
    assert barrier["kind"] == "barrier"
    assert barrier["barrier"]["mode"] == "all"
    assert barrier["barrier"]["on_partial"] == "fail"
    assert barrier["barrier"]["verify_artifact_exists"] is True
    assert barrier["joins"] == ["run-units"]
    integrate = K.stage(doc, "integrate-serially")
    assert integrate["depends_on"] == ["empty-index-gate"]


def check_downgrade_is_recorded_not_silent(doc: Mapping[str, Any]) -> None:
    downgrade = K.stage(doc, "serial-downgrade")
    assert downgrade.get("when") == "worktree_available == false"
    paths = {artifact["path"] for artifact in downgrade["produces"]}
    assert "command-center/isolation/downgrade-record.json" in paths, (
        "a run that is less isolated than it claims must say so on disk"
    )
    assert "downgrade-record" in doc["outputs"]


def check_it_delegates_the_quality_loop_rather_than_reimplementing_it(
    doc: Mapping[str, Any],
) -> None:
    child = K.stage(doc, "build-in-worktree")
    assert child["kind"] == "subworkflow"
    assert child["workflow"]["workflow_id"] == "per-unit-four-phase-pipeline"
    assert child["isolation"] == "worktree"
    assert "per-unit-four-phase-pipeline" in doc["subworkflows"]
    # and it must NOT redeclare the four phases itself
    ids = set(K.stage_ids(doc))
    assert not {"implement", "adversarial-review", "commit"} & ids, (
        "the isolation substrate must not grow its own copy of the quality loop"
    )


def check_isolation_outcome_is_asserted(doc: Mapping[str, Any]) -> None:
    gate = K.gate(doc, "isolation-preserved")
    assert "cross_unit_files_in_any_commit == 0" in gate["expression"]
    assert "sibling_work_lost == 0" in gate["expression"]
    assert gate["blocking"] is True


ALL_CHECKS = (
    check_worktrees_are_pre_created_before_any_unit_runs,
    check_branches_are_cut_from_an_explicit_base_ref,
    check_empty_index_trap_is_gated_before_commit,
    check_broad_add_is_denied_by_policy_and_by_gate,
    check_integration_is_serial_behind_a_hard_barrier,
    check_downgrade_is_recorded_not_silent,
    check_it_delegates_the_quality_loop_rather_than_reimplementing_it,
    check_isolation_outcome_is_asserted,
)


@pytest.mark.parametrize("check", ALL_CHECKS, ids=lambda c: c.__name__)
def test_shipped_blueprint_satisfies_every_mechanism_check(check: Any) -> None:
    check(DOC)


def test_shipped_blueprint_is_conformant() -> None:
    assert K.schema_errors(DOC) == []
    assert K.semantic_violations(DOC) == []


# ------------------------------------------------------------------------- mutation controls


def _start_units_before_provisioning(doc: dict) -> None:
    stages = doc["stages"]
    pre = next(i for i, s in enumerate(stages) if s["id"] == "pre-create-worktrees")
    run = next(i for i, s in enumerate(stages) if s["id"] == "run-units")
    stages[pre], stages[run] = stages[run], stages[pre]


def _default_base_ref_to_head(doc: dict) -> None:
    doc["params"]["base_ref"]["default"] = "HEAD"


def _drop_the_empty_index_gate(doc: dict) -> None:
    doc["gates"]["empty-index-guard"]["expression"] = "commit_created == true"


def _allow_broad_add(doc: dict) -> None:
    doc["tool_policy"]["deny"] = ["WebFetch", "WebSearch"]


def _soften_the_integration_barrier(doc: dict) -> None:
    K.find_stage_mut(doc, "integration-barrier")["barrier"]["on_partial"] = (
        "proceed-degraded"
    )


def _silence_the_downgrade(doc: dict) -> None:
    K.find_stage_mut(doc, "serial-downgrade")["produces"] = [
        {
            "path": "command-center/isolation/scratch.json",
            "schema_ref": "command-center/schema/decision-record.schema.json",
            "min_bytes": 128,
        }
    ]


def _inline_the_quality_loop(doc: dict) -> None:
    body = K.find_stage_mut(doc, "run-units")["body"]
    body.append(
        {
            "id": "commit",
            "title": "A locally reimplemented commit phase",
            "kind": "task",
            "role": "integrator",
            "work_unit_ref": "IMP-0428",
        }
    )


def _drop_the_isolation_assertion(doc: dict) -> None:
    doc["gates"]["isolation-preserved"]["expression"] = "integration_completed == true"


MUTATIONS = (
    (
        check_worktrees_are_pre_created_before_any_unit_runs,
        _start_units_before_provisioning,
    ),
    (check_branches_are_cut_from_an_explicit_base_ref, _default_base_ref_to_head),
    (check_empty_index_trap_is_gated_before_commit, _drop_the_empty_index_gate),
    (check_broad_add_is_denied_by_policy_and_by_gate, _allow_broad_add),
    (
        check_integration_is_serial_behind_a_hard_barrier,
        _soften_the_integration_barrier,
    ),
    (check_downgrade_is_recorded_not_silent, _silence_the_downgrade),
    (
        check_it_delegates_the_quality_loop_rather_than_reimplementing_it,
        _inline_the_quality_loop,
    ),
    (check_isolation_outcome_is_asserted, _drop_the_isolation_assertion),
)


@pytest.mark.parametrize(
    "check,mutate", MUTATIONS, ids=lambda v: getattr(v, "__name__", "")
)
def test_each_check_fails_on_its_mutated_blueprint(check: Any, mutate: Any) -> None:
    broken = K.mutant(DOC, mutate)
    assert K.raises_assertion(check, broken), (
        f"{check.__name__} stayed silent on the mutated blueprint, so it measures nothing"
    )


def test_the_head_default_mutation_is_schema_legal() -> None:
    """`base_ref: HEAD` is valid DSL - only this test rejects it, which is why it exists."""
    broken = K.mutant(DOC, _default_base_ref_to_head)
    assert K.schema_errors(broken) == []
    assert K.raises_assertion(check_branches_are_cut_from_an_explicit_base_ref, broken)
