"""End-to-end tests for blueprint 77, BP-UX-01 design-studio-eight-gate-loop (FLAGSHIP).

The two properties that make this a pipeline rather than a checklist are (a) exactly ONE stage
may write app source and a repair loop reverts it under an INDEPENDENT verify, and (b) the mode
router is declarative - every gate carries its own entry condition, so gate skipping is auditable
instead of implicit in a skill's prose. Both get a mutation control.

The card's own UNVERIFIED item is gate-skip correctness. This file asserts the router condition
is PRESENT on every gate; it does NOT prove that a gate entered mid-pipeline finds its inputs -
that needs nine live runs and is named as the settling experiment.
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent)):
    if _p not in sys.path:  # pragma: no cover - import plumbing
        sys.path.insert(0, _p)

import bp7_checks as C  # noqa: E402
import bp7_testkit as K  # noqa: E402
from wfdsl import schemas, semantics  # noqa: E402

BP = "design-studio-eight-gate-loop"


def test_schema_valid_and_semantically_clean() -> None:
    doc = K.load(BP)
    errs = list(schemas.workflow_validator().iter_errors(doc))
    assert errs == [], [
        f"{'/'.join(str(p) for p in e.absolute_path)} [{e.validator}]" for e in errs[:5]
    ]
    assert [r.to_json() for r in semantics.check_workflow(doc) if r.violations] == []


def test_it_is_a_meta_workflow_that_delegates_two_gates_to_sibling_blueprints() -> None:
    """The card says this is 'the full pipeline that calls [the audit] as one gate'. Declaring the
    containment as a real subworkflow reference is what makes that claim checkable rather than a
    sentence - and it is why 77 is not a duplicate of 78 or 80."""
    doc = K.load(BP)
    assert doc["kind"] == "meta-workflow"
    declared = set(doc["subworkflows"])
    assert declared == {
        "code-to-canvas-mirror-round-trip",
        "two-track-ui-audit-rubric-verdict",
    }
    for sid, wf in (
        ("g2-transpose", "code-to-canvas-mirror-round-trip"),
        ("g3-critique", "two-track-ui-audit-rubric-verdict"),
    ):
        st = C.stage(doc, sid)
        assert st is not None and st["kind"] == "subworkflow"
        assert st["workflow"]["workflow_id"] == wf
    # and the referenced documents exist on disk, so the reference is not dangling
    for wf in declared:
        K.load(wf)


def test_every_inline_work_unit_passes_the_strict_profile() -> None:
    validator = schemas.work_unit_validator("strict")
    units = C.work_units(K.load(BP))
    assert len(units) == 8
    assert {u["id"] for u in units if list(validator.iter_errors(u))} == set()


# ------------------------------- property 1: one source-write stage, reverted on failure


def test_exactly_one_source_write_stage_with_an_independent_revert() -> None:
    result = C.exactly_one_source_write_stage_with_revert(K.load(BP))
    assert result.ok, result.why()


def test_control_granting_a_second_role_source_write_access_is_caught() -> None:
    """Both-states control: if the driver can also edit source, 'the implement gate is the only
    stage that writes app source' stops being true and the revert record no longer covers every
    change."""
    mutated = K.mutate(
        K.load(BP), K.grant_role_write_paths("driver", ["app/**", "src/**"])
    )
    K.assert_still_schema_valid(mutated)
    result = C.exactly_one_source_write_stage_with_revert(mutated)
    assert not result.ok, (
        "the predicate accepted two roles with app-source write access"
    )
    assert any("exactly one authoring role" in r for r in result.reasons), (
        result.reasons
    )


def test_control_retargeting_the_revert_loop_away_from_the_implement_stage_is_caught() -> (
    None
):
    """Both-states control: a revert loop pointed at the wrong stage reverts nothing that matters."""
    mutated = K.mutate(K.load(BP), K.retarget_repair_loop("revert-gate", ["g6-drive"]))
    K.assert_still_schema_valid(mutated)
    result = C.exactly_one_source_write_stage_with_revert(mutated)
    assert not result.ok, (
        "the predicate accepted a revert loop that does not target the writer"
    )
    assert any("not the source-write stage" in r for r in result.reasons), (
        result.reasons
    )


def test_control_making_the_reverter_the_same_role_as_the_implementer_is_caught() -> (
    None
):
    """Both-states control: an author certifying its own undo is the failure the separate reverter
    role exists to prevent."""

    def apply(doc: dict) -> None:
        K.find_stage(doc, "apply-revert")["role"] = "implementer"

    mutated = K.mutate(K.load(BP), apply)
    K.assert_still_schema_valid(mutated)
    result = C.exactly_one_source_write_stage_with_revert(mutated)
    assert not result.ok, (
        "the predicate accepted the implementer reverting its own change"
    )
    assert any("same role as the implementer" in r for r in result.reasons), (
        result.reasons
    )


# ------------------------------------------------ property 2: the router is declarative


def test_every_gate_declares_its_router_entry_condition() -> None:
    result = C.every_gate_declares_its_router_entry(K.load(BP))
    assert result.ok, result.why()


def test_control_removing_one_gates_router_condition_is_caught() -> None:
    """Both-states control: a gate with no entry condition runs on every mode, which silently
    defeats the router the whole design is built around."""
    mutated = K.mutate(K.load(BP), K.drop_stage_when("g4-iterate"))
    K.assert_still_schema_valid(mutated)
    result = C.every_gate_declares_its_router_entry(mutated)
    assert not result.ok, "a gate with no router condition was accepted"
    assert any("g4-iterate" in r for r in result.reasons), result.reasons


# ------------------------------------------------------- property 3: bounded iteration


def test_the_iterate_loop_exits_on_no_progress_not_only_on_success() -> None:
    conv = C.stage(K.load(BP), "g4-iterate")["convergence"]
    assert conv["no_progress_rounds"] == 2, conv
    assert conv["max_iterations"] <= 6, conv
    ids = C.identifiers(conv["converged_when"])
    assert "target_composite" in ids and "composite_score" in ids
    # target_composite must be a declared param, or the exit condition references nothing
    assert "target_composite" in K.load(BP)["params"]


def test_source_writes_are_opt_in_and_gated_before_the_implement_stage() -> None:
    doc = K.load(BP)
    assert doc["params"]["allow_source_writes"]["default"] is False
    ids = C.identifiers(C.gate_expression(doc, "g5-authorisation"))
    assert "allow_source_writes" in ids
    assert "g5-authorisation" in C.ancestors(doc, "g5-implement")


def test_the_worked_example_shows_a_partial_revert_not_a_clean_win() -> None:
    """The interesting case is the one where 4 of 5 edits survive and 1 is reverted; an example
    that only shows success would not demonstrate the attribution step."""
    ext = K.load(BP)["x_extensions"]["bp7"]
    example = ext["worked_example"]
    trace = " ".join(example["expected_trace"])
    assert "REGRESSED" in trace
    assert (
        "byte-restores that line only" in trace
        or "partial revert" in example["expected_terminal_state"]
    )
    assert "UNVERIFIED gate-skip correctness" in ext["unverified"]
    assert "settling experiment" in ext["unverified"].lower()
