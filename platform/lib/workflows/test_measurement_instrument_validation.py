"""End-to-end tests for blueprint 74, BP-DAT-03 measurement-instrument-validation (FLAGSHIP).

The blueprint's whole claim is ORDERING: four construction checks, then a known-present control,
then a verdict - with a self-contradicting run halting before anything else is read. Ordering is
exactly the property a document can silently lose, so every ordering test carries a mutation
control that breaks one edge and requires the same predicate to fire.
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

BP = "measurement-instrument-validation"


def test_document_is_schema_valid_and_semantically_clean() -> None:
    doc = K.load(BP)
    errs = list(schemas.workflow_validator().iter_errors(doc))
    assert errs == [], [
        f"{'/'.join(str(p) for p in e.absolute_path)} [{e.validator}]" for e in errs[:5]
    ]
    assert [r.to_json() for r in semantics.check_workflow(doc) if r.violations] == []


def test_it_is_declared_a_subworkflow_because_it_is_a_pass_other_workflows_call() -> (
    None
):
    assert K.load(BP)["kind"] == "subworkflow"


def test_every_inline_work_unit_passes_the_strict_profile() -> None:
    validator = schemas.work_unit_validator("strict")
    units = C.work_units(K.load(BP))
    assert len(units) == 6
    assert {
        u["id"]: list(validator.iter_errors(u))
        for u in units
        if list(validator.iter_errors(u))
    } == {}


# ------------------------------------------------- property 1: four shapes, then control


def test_four_shapes_precede_the_control() -> None:
    result = C.four_shapes_precede_the_control(K.load(BP))
    assert result.ok, result.why()


def test_control_breaking_the_shape_chain_is_caught() -> None:
    """Both-states control: if the comparator check no longer follows the self-match check, the
    chain has silently become a set of unordered probes."""
    mutated = K.mutate(
        K.load(BP), K.drop_dependency("shape-comparator", "shape-self-match")
    )
    K.assert_still_schema_valid(mutated)
    result = C.four_shapes_precede_the_control(mutated)
    assert not result.ok, "the predicate accepted a broken shape chain"
    assert any("the chain is broken" in r for r in result.reasons), result.reasons


def test_control_running_the_known_present_control_before_the_shapes_is_caught() -> (
    None
):
    """Both-states control: a control run before the construction checks cannot rescue a zero
    produced by a self-defeating instrument, because the instrument has not been inspected yet."""
    mutated = K.mutate(
        K.load(BP), K.drop_dependency("known-present-control", "shape-harness-fit")
    )
    K.assert_still_schema_valid(mutated)
    result = C.four_shapes_precede_the_control(mutated)
    assert not result.ok, (
        "the predicate accepted a control that runs before the shape checks"
    )
    assert any("does not run after" in r for r in result.reasons), result.reasons


# ------------------------------------------- property 2: a self-contradiction HALTS


def test_self_contradiction_halts_the_analysis() -> None:
    result = C.self_contradiction_halts_the_analysis(K.load(BP))
    assert result.ok, result.why()


def test_control_downgrading_the_halt_gate_to_record_and_continue_is_caught() -> None:
    """Both-states control: this is the measured failure - `grep -c pat || echo 0` reported both
    all-seven-hit and an empty intersection in one run, and the next action would have re-patched
    seven PRs. A gate that records and continues would have let that happen."""
    mutated = K.mutate(
        K.load(BP), K.set_gate_on_fail("not-self-contradictory", "record-and-continue")
    )
    K.assert_still_schema_valid(mutated)
    result = C.self_contradiction_halts_the_analysis(mutated)
    assert not result.ok, "a non-halting self-contradiction gate was accepted"
    assert any("does not halt the analysis" in r for r in result.reasons), (
        result.reasons
    )


def test_control_making_the_verdict_reachable_without_the_halt_gate_is_caught() -> None:
    mutated = K.mutate(
        K.load(BP), K.drop_dependency("shape-self-match", "halt-on-self-contradiction")
    )
    K.assert_still_schema_valid(mutated)
    result = C.self_contradiction_halts_the_analysis(mutated)
    assert not result.ok, "the predicate accepted a path around the halt gate"
    assert any(
        "reachable without passing the halt gate" in r for r in result.reasons
    ), result.reasons


# ---------------------------------------------- property 3: a zero needs a control


def test_a_zero_is_never_accepted_without_a_known_present_control() -> None:
    doc = K.load(BP)
    ids = C.identifiers(C.gate_expression(doc, "zero-control-gate"))
    assert "known_present_control_found_it" in ids
    assert "measurement_is_zero" in ids
    assert "zero-control-gate" in C.ancestors(doc, "emit-verdict")


def test_no_retry_anywhere_because_re_reading_the_same_text_is_not_a_second_signal() -> (
    None
):
    doc = K.load(BP)
    assert doc["retry_policy"]["strategy"] == "none"
    assert doc["retry_policy"]["max_attempts"] == 1
    # every unit's retry_policy prose must SAY why, not just "none"
    for unit in C.work_units(doc):
        assert len(unit["retry_policy"]) >= 10, unit["id"]


def test_the_checklist_admits_its_own_scope_limit() -> None:
    """A four-shape checklist cannot see a fifth failure mode. The artifact must say so inline,
    not bury it - an unqualified 'validated' verdict would be the overclaim."""
    ext = K.load(BP)["x_extensions"]["bp7"]
    assert "UNVERIFIED" in ext["unverified"]
    assert (
        "novel instrument failure" in ext["unverified"]
        or "fifth reason" in ext["unverified"]
    )
    verdict_unit = [u for u in C.work_units(K.load(BP)) if u["id"].endswith("06")][0]
    assert any(
        "out-of-scope" in t or "four shapes checked" in t
        for t in verdict_unit["tests_required"]
    )


def test_the_worked_example_ends_in_a_failure_because_that_is_the_correct_outcome() -> (
    None
):
    """The example's instrument IS broken, so a SUCCESS terminal state would be the wrong answer."""
    example = K.load(BP)["x_extensions"]["bp7"]["worked_example"]
    assert example["expected_terminal_state"].startswith("FAILED:DAT-74")
    assert "instrument-self-contradiction" in example["expected_terminal_state"]
    assert any(
        "NOT re-patched" in t or "not re-patched" in t
        for t in example["expected_trace"]
    )
