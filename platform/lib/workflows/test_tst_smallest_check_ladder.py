"""End-to-end test for FLAGSHIP blueprint BP-TST-01 (card 54), tst.smallest-check-ladder.

Mechanism protected: DETERMINISTIC selection only, escalate-never-skip, longrun above the
threshold, and a cross-cutting change may not be certified by an L1 run.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bp5_testkit as kit  # noqa: E402
from wfdsl import expr as _expr  # noqa: E402

SLUG = "tst.smallest-check-ladder"


def doc() -> dict:
    return kit.load(SLUG)


def test_validates_on_disk() -> None:
    kit.assert_accepted(doc())


def test_ml_predictive_selection_is_refused_not_merely_discouraged() -> None:
    d = doc()
    gate = d["gates"]["deterministic-selection-only"]
    assert gate["on_fail"] == "fail" and gate["blocking"] is True
    assert kit.evaluate_gate(d, "deterministic-selection-only") is True
    assert (
        kit.evaluate_gate(
            d, "deterministic-selection-only", {"ml_predictive_selection_used": True}
        )
        is False
    )
    assert (
        kit.evaluate_gate(
            d, "deterministic-selection-only", {"selector_family": "PREDICTIVE"}
        )
        is False
    )
    assert "none" in d["params"]["selector"]["enum"], (
        "the no-selector case must be expressible"
    )


def test_a_cross_cutting_change_cannot_be_certified_by_l1() -> None:
    """The measured false-confidence case the card names."""
    d = doc()
    assert kit.evaluate_gate(d, "level-is-sufficient") is True
    assert (
        kit.evaluate_gate(
            d, "level-is-sufficient", {"cross_cutting_change": True, "level_index": 1}
        )
        is False
    )
    # a NON cross-cutting change is still allowed to stop at L1 - the gate discriminates
    assert (
        kit.evaluate_gate(
            d, "level-is-sufficient", {"cross_cutting_change": False, "level_index": 1}
        )
        is True
    )


def test_a_missing_selector_escalates_and_never_skips() -> None:
    d = doc()
    assert kit.evaluate_gate(d, "escalate-not-skip") is True
    assert (
        kit.evaluate_gate(
            d, "escalate-not-skip", {"levels_skipped_due_to_missing_selector": 1}
        )
        is False
    )


def test_a_long_level_must_run_under_longrun_not_in_the_foreground() -> None:
    """AGENTS.md 4a: a blocking foreground call is what the heartbeat rule exists to prevent."""
    d = doc()
    assert kit.evaluate_gate(d, "longrun-wrapped") is True
    assert (
        kit.evaluate_gate(d, "longrun-wrapped", {"blocking_foreground_call_used": True})
        is False
    )
    assert (
        kit.evaluate_gate(
            d, "longrun-wrapped", {"runs_over_threshold_wrapped_in_longrun": False}
        )
        is False
    )
    assert "Bash:longrun" in d["tool_policy"]["allow"], (
        "longrun is mandated but not permitted"
    )


def test_the_escalation_loop_is_bounded_to_the_four_ladder_levels() -> None:
    d = doc()
    loop = next(s for s in d["stages"] if s["id"] == "run-ladder")
    conv = loop["convergence"]
    assert conv["max_iterations"] == 4, "the ladder has exactly four levels L0-L3"
    assert conv["on_no_convergence"] == "fail", (
        "an exhausted ladder must not report success"
    )
    assert (
        "level_passed" in conv["converged_when"]
        and "level_index" in conv["converged_when"]
    )


def test_the_classifier_fails_safe_upward() -> None:
    """A wrong classification must err toward MORE testing, never less."""
    d = doc()
    unit = next(
        u
        for s in d["stages"]
        if s["id"] == "classify-blast-radius"
        for u in [s["work_unit"]]
    )
    assert (
        "fail safe upward" in unit["retry_policy"]
        or "CROSS-CUTTING" in unit["retry_policy"]
    )
    assert any(
        "CROSS-CUTTING" in t or "cross-cutting" in t for t in unit["tests_required"]
    )


def test_the_receipt_discloses_what_the_level_does_not_cover() -> None:
    """Anti-overclaim: an L1 green must not be readable as a full-suite green."""
    d = doc()
    unit = next(
        u
        for s in d["stages"]
        if s["id"] == "emit-level-receipt"
        for u in [s["work_unit"]]
    )
    assert (
        "not-covered" in unit["question_or_target"]
        or "does NOT cover" in unit["question_or_target"]
    )
    assert unit["output_schema"].endswith("test-receipt.schema.json")


def test_MUTATION_weakening_the_cross_cutting_gate_removes_its_power() -> None:
    d = doc()
    bad = {"cross_cutting_change": True, "level_index": 1}
    assert kit.evaluate_gate(d, "level-is-sufficient", bad) is False

    weakened = kit.mutated(d)
    weakened["gates"]["level-is-sufficient"]["expression"] = "level_index >= 0"
    ctx = kit.worked_context(weakened)
    ctx.update(bad)
    assert (
        _expr.evaluate(
            weakened["gates"]["level-is-sufficient"]["expression"], ctx, strict=True
        )
        is True
    )


def test_MUTATION_dropping_the_selection_gate_is_rejected() -> None:
    kit.assert_rejected(
        kit.drop_stage(doc(), "deterministic-selection-only"),
        "selection-discipline gate removed",
    )


def test_MUTATION_unbounding_the_ladder_loop_is_rejected() -> None:
    d = kit.mutated(doc())
    loop = next(s for s in d["stages"] if s["id"] == "run-ladder")
    del loop["convergence"]["max_iterations"]
    kit.assert_rejected(d, "escalation loop left without an iteration bound")


def test_MUTATION_a_convergence_metric_that_is_not_declared_is_rejected() -> None:
    """DSL-SEM-008: a convergence rule referencing an undeclared metric can never be evaluated."""
    d = kit.mutated(doc())
    loop = next(s for s in d["stages"] if s["id"] == "run-ladder")
    loop["convergence"]["converged_when"] = "undeclared_progress_metric == true"
    kit.assert_rejected(d, "convergence on an undeclared metric")
