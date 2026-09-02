"""End-to-end test for FLAGSHIP blueprint BP-CRV-04 (card 52), crv.bug-class-variant-sweep.

The mechanism this protects: the DETECTOR CONTROL runs before the search, so a zero-result
sweep is interpretable. Every test below reads the document from disk.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bp5_testkit as kit  # noqa: E402

SLUG = "crv.bug-class-variant-sweep"


def doc() -> dict:
    return kit.load(SLUG)


def test_validates_on_disk() -> None:
    kit.assert_accepted(doc())


def test_the_detector_control_precedes_the_sweep() -> None:
    """Ordering IS the mechanism. A control that runs after the search cannot make a zero
    result interpretable, because the sweep has already been believed."""
    d = doc()
    kit.assert_precedes(d, "detector-control", "sweep-scope")
    kit.assert_precedes(d, "generalise-pattern", "detector-control")
    order = kit.top_stage_order(d)
    assert order.index("detector-control") < order.index("sweep-scope")
    assert d["gates"]["detector-control"]["on_fail"] != "record-and-continue", (
        "a detector control that records and continues is not a control"
    )


def test_narrowing_loop_is_bounded_and_cannot_lose_the_known_instance() -> None:
    d = doc()
    loop = next(s for s in d["stages"] if s["id"] == "narrow-noisy-pattern")
    conv = loop["convergence"]
    assert conv["max_iterations"] <= 6, "an unbounded narrowing loop can grind forever"
    assert conv["no_progress_rounds"] >= 1, "no anti-grind exit"
    # the convergence condition must still require the known instance to be found
    assert "pattern_finds_known_instance" in conv["converged_when"], (
        "the loop could converge on a pattern that no longer finds the known instance"
    )
    metrics = {m["name"] for m in conv["metrics"]}
    assert {"hits", "pattern_finds_known_instance"} <= metrics


def test_remediation_set_not_first_file_is_the_unit_of_done() -> None:
    d = doc()
    expr = d["gates"]["remediation-set-is-the-unit"]["expression"]
    assert "single_file_declared_done" in expr
    assert kit.evaluate_gate(d, "remediation-set-is-the-unit") is True
    assert (
        kit.evaluate_gate(
            d, "remediation-set-is-the-unit", {"single_file_declared_done": True}
        )
        is False
    ), "a one-file done claim on a 6-instance class must fail the gate"


def test_graduation_to_ci_is_an_owner_decision_not_an_agent_one() -> None:
    d = doc()
    stage = next(s for s in d["stages"] if s["id"] == "graduate-decision")
    assert stage["kind"] == "human_checkpoint"
    assert stage["approval_mode"] == "owner-only"
    assert stage["owner_approval_required"] is True
    assert stage["on_timeout"] != "proceed", (
        "an unanswered graduation must not silently promote a blocking CI gate"
    )
    assert len(stage["options"]) >= 3


def test_detector_control_gate_rejects_a_pattern_that_misses_the_known_instance() -> (
    None
):
    """The failure this blueprint exists to prevent."""
    d = doc()
    assert kit.evaluate_gate(d, "detector-control") is True
    assert (
        kit.evaluate_gate(
            d, "detector-control", {"pattern_finds_known_instance": False}
        )
        is False
    )


def test_MUTATION_weakening_the_detector_control_removes_its_power() -> None:
    """Both-states control on the MECHANISM. Replace the gate's condition with a tautology and
    confirm the bad state now passes - which proves the real condition is what does the work,
    not the presence of a gate named 'detector-control'."""
    d = doc()
    bad = {"pattern_finds_known_instance": False}
    assert kit.evaluate_gate(d, "detector-control", bad) is False

    weakened = kit.mutated(d)
    weakened["gates"]["detector-control"]["expression"] = "hits >= 0"
    import _bp5_testkit as k
    from wfdsl import expr as _expr

    ctx = k.worked_context(weakened)
    ctx.update(bad)
    assert (
        _expr.evaluate(
            weakened["gates"]["detector-control"]["expression"], ctx, strict=True
        )
        is True
    ), (
        "the mutated gate should have stopped rejecting - if it still rejects, this test was "
        "not measuring the condition it claims to measure"
    )


def test_MUTATION_dropping_the_detector_control_stage_is_rejected() -> None:
    """Both-states control on the DOCUMENT. Deleting the control stage while later stages still
    depend on it must be caught by DSL-SEM-002."""
    kit.assert_rejected(
        kit.drop_stage(doc(), "detector-control"), "detector-control stage removed"
    )


def test_MUTATION_unbounding_the_sweep_fanout_is_rejected() -> None:
    d = kit.mutated(doc())
    stage = next(s for s in d["stages"] if s["id"] == "sweep-scope")
    del stage["max_concurrency"]
    kit.assert_rejected(d, "sweep fan-out left without a concurrency bound")


def test_MUTATION_barrier_without_a_partial_policy_is_rejected() -> None:
    d = kit.mutated(doc())
    stage = next(s for s in d["stages"] if s["id"] == "sweep-scope")
    del stage["barrier"]["on_partial"]
    kit.assert_rejected(d, "barrier that silently drops straggler shards")
