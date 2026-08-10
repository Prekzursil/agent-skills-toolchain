"""End-to-end tests for blueprint 81, BP-UX-05 design-first-ui-intake (FLAGSHIP).

Nothing is BUILT by this blueprint - the contribution is routing plus one structural property, so
the tests are almost entirely about reachability:
  * the implement stage must be UNREACHABLE until a design direction is on disk, and
  * a non-UI request must pass through untouched, because a router that captures everything is
    worse than no router.
A degraded run (design tools unavailable) must RECORD the gap, since the whole point is to make a
repeatedly-flagged behaviour countable rather than invisible.
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

BP = "design-first-ui-intake"


def test_schema_valid_and_semantically_clean() -> None:
    doc = K.load(BP)
    errs = list(schemas.workflow_validator().iter_errors(doc))
    assert errs == [], [f"{'/'.join(str(p) for p in e.absolute_path)} [{e.validator}]" for e in errs[:5]]
    assert [r.to_json() for r in semantics.check_workflow(doc) if r.violations] == []


def test_every_inline_work_unit_passes_the_strict_profile() -> None:
    validator = schemas.work_unit_validator("strict")
    units = C.work_units(K.load(BP))
    assert len(units) == 6
    assert {u["id"] for u in units if list(validator.iter_errors(u))} == set()


# ------------------------------------------ property 1: the admission gate is structural


def test_implementation_is_unreachable_without_a_recorded_direction() -> None:
    result = C.implementation_unreachable_without_a_direction(K.load(BP))
    assert result.ok, result.why()


def test_control_letting_implement_bypass_the_admission_gate_is_caught() -> None:
    """Both-states control: this is the flagged behaviour itself - an implementation agent spawned
    before any design direction exists. Remove the edge and the predicate must fire."""
    mutated = K.mutate(K.load(BP), K.drop_dependency("implement", "admission-gate"))
    K.assert_still_schema_valid(mutated)
    result = C.implementation_unreachable_without_a_direction(mutated)
    assert not result.ok, "the predicate accepted an implement stage that bypasses the admission gate"
    assert any("does not transitively depend on the admission gate" in r for r in result.reasons), result.reasons


def test_control_weakening_the_admission_gate_expression_is_caught() -> None:
    """Both-states control: a gate that no longer checks for a recorded direction admits everything."""
    mutated = K.mutate(K.load(BP), K.weaken_gate("direction-admitted", "request_is_ui == true"))
    K.assert_still_schema_valid(mutated)
    result = C.implementation_unreachable_without_a_direction(mutated)
    assert not result.ok, "an admission gate that ignores the direction was accepted"
    assert any("does not require a recorded direction" in r for r in result.reasons), result.reasons


def test_control_downgrading_the_admission_gate_to_non_blocking_is_caught() -> None:
    mutated = K.mutate(K.load(BP), K.set_gate_on_fail("direction-admitted", "record-and-continue"))
    K.assert_still_schema_valid(mutated)
    result = C.implementation_unreachable_without_a_direction(mutated)
    assert not result.ok, "a non-blocking admission gate was accepted"
    assert any("does not block" in r for r in result.reasons), result.reasons


# -------------------------------------------- property 2: no false routing of non-UI work


def test_a_non_ui_request_passes_through_untouched() -> None:
    result = C.non_ui_request_passes_through(K.load(BP))
    assert result.ok, result.why()


def test_control_removing_the_ui_guard_from_the_implement_stage_is_caught() -> None:
    """Both-states control: without the guard, a 'fix the CSV parser' request would be routed
    through design intake. Over-capturing is the failure mode that makes a router worse than none."""
    mutated = K.mutate(K.load(BP), K.drop_stage_when("implement"))
    K.assert_still_schema_valid(mutated)
    result = C.non_ui_request_passes_through(mutated)
    assert not result.ok, "a stage that runs unconditionally on a non-UI request was accepted"
    assert any("runs unconditionally" in r for r in result.reasons), result.reasons


def test_control_weakening_the_false_routing_control_is_caught() -> None:
    mutated = K.mutate(K.load(BP), K.weaken_gate("no-false-routing", "request_is_ui == true"))
    K.assert_still_schema_valid(mutated)
    result = C.non_ui_request_passes_through(mutated)
    assert not result.ok, "a routing control that cannot detect a false capture was accepted"
    assert any("false_routing_detected" in r for r in result.reasons), result.reasons


# ------------------------------------- property 3: a degraded run records the gap loudly


def test_a_degraded_run_records_the_gap_instead_of_reverting_silently_to_code_first() -> None:
    doc = K.load(BP)
    ids = C.identifiers(C.gate_expression(doc, "degradation-gate"))
    assert {"design_tools_available", "design_gap_recorded"} <= ids, ids
    gap = C.stage(doc, "record-design-gap")
    assert gap is not None
    assert "design_tools_available == false" in gap["when"], gap["when"]
    unit = gap["work_unit"]
    assert any("NOT written when the tools were available" in t for t in unit["tests_required"]), (
        "the gap counter must be provably conditional, or the count means nothing"
    )


def test_a_skipped_canvas_is_recorded_rather_than_assumed() -> None:
    doc = K.load(BP)
    skip = C.stage(doc, "record-canvas-skip")
    assert skip is not None
    assert "skip_canvas == true" in skip["when"]
    canvas = C.stage(doc, "produce-canvas")
    assert "skip_canvas == false" in canvas["when"], "the two branches are not mutually exclusive"
    # the admission gate still runs after either branch, so the shortcut cannot bypass it
    deps = set(C.stage(doc, "admission-gate")["depends_on"])
    assert {"produce-canvas", "record-canvas-skip"} <= deps, deps


def test_the_owner_decision_is_carried_as_a_checkpoint_not_buried_in_prose() -> None:
    """The card records an OWNER-DECISION (hook enforcement vs documented default). A blueprint
    that mentions it only in prose cannot surface it at runtime."""
    cp = C.stage(K.load(BP), "enforcement-decision")
    assert cp is not None and cp["kind"] == "human_checkpoint"
    assert cp["approval_mode"] == "owner-only"
    assert cp["on_timeout"] in ("fail", "escalate", "proceed")
    assert "timeout_seconds" in cp, "an unanswered checkpoint must resolve to a declared state, never hang"
    assert set(cp["options"]) == {"enforce-with-hook", "documented-default", "revisit-after-more-data"}


def test_the_worked_example_covers_both_the_ui_and_the_non_ui_request() -> None:
    ext = K.load(BP)["x_extensions"]["bp7"]
    trace = " ".join(ext["worked_example"]["expected_trace"])
    assert "NOT UI" in trace, "the example never exercises the pass-through path"
    assert "passes through untouched" in trace
    assert "likely (55-80%)" in ext["unverified"], "the routing-suffices claim must carry its band"
