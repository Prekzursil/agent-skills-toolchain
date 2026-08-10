"""End-to-end test for FLAGSHIP blueprint BP-TST-06 (card 59),
tst.fail-first-red-proof-certification.

Mechanism protected: a test that PASSES at the pre-change ref is not a regression proof; the red
capture must be the runner's real stored output; an unbuildable pre-change tree yields UNAVAILABLE
rather than an assumed pass; and a pure addition gets a mutation substitute, never a fake red.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bp5_testkit as kit  # noqa: E402
from wfdsl import expr as _expr  # noqa: E402

SLUG = "tst.fail-first-red-proof-certification"


def doc() -> dict:
    return kit.load(SLUG)


def test_validates_on_disk() -> None:
    kit.assert_accepted(doc())


def test_red_is_checked_before_green_and_both_before_certification() -> None:
    """Order is the mechanism: certifying before the pre-change run is just trusting the author."""
    d = doc()
    kit.assert_precedes(d, "run-at-pre-change", "red-before")
    kit.assert_precedes(d, "red-before", "run-at-post-change")
    kit.assert_precedes(d, "green-after", "certify-or-refuse")
    kit.assert_precedes(d, "capture-is-real-output", "certify-or-refuse")


def test_a_test_that_passes_pre_change_is_refused_as_a_proof() -> None:
    """The single most common way a green suite lies."""
    d = doc()
    assert d["gates"]["red-before"]["on_fail"] == "fail"
    assert kit.evaluate_gate(d, "red-before") is True
    assert kit.evaluate_gate(d, "red-before", {"tests_passing_at_pre_change_ref": 1}) is False


def test_a_test_still_failing_after_the_change_certifies_nothing() -> None:
    d = doc()
    assert kit.evaluate_gate(d, "green-after") is True
    assert kit.evaluate_gate(d, "green-after", {"tests_failing_at_post_change_ref": 1}) is False


def test_the_red_capture_must_be_stored_runner_output_not_an_assertion() -> None:
    d = doc()
    assert kit.evaluate_gate(d, "capture-is-real-output") is True
    assert kit.evaluate_gate(d, "capture-is-real-output", {"red_capture_source": "AGENT_CLAIM"}) is False
    assert kit.evaluate_gate(d, "capture-is-real-output", {"asserted_without_capture": 1}) is False
    assert d["params"]["evidence_store"]["default"].startswith("command-center/")


def test_an_unbuildable_pre_tree_yields_unavailable_and_is_never_assumed() -> None:
    d = doc()
    gate = d["gates"]["pre-tree-buildable"]
    assert gate["on_fail"] == "record-and-continue" and gate["blocking"] is False
    assert kit.evaluate_gate(d, "pre-tree-buildable") is True
    # unbuildable AND not marked unavailable -> the gate must not hold
    assert (
        kit.evaluate_gate(
            d, "pre-tree-buildable", {"pre_change_tree_built": False, "certification_marked_unavailable": False}
        )
        is False
    )
    # unbuildable BUT honestly marked -> acceptable, degraded
    assert (
        kit.evaluate_gate(
            d, "pre-tree-buildable", {"pre_change_tree_built": False, "certification_marked_unavailable": True}
        )
        is True
    )


def test_a_pure_addition_routes_to_a_mutation_substitute_not_a_fake_red() -> None:
    """Forcing a red on behaviour that never existed would be fabrication."""
    d = doc()
    stage = next(s for s in d["stages"] if s["id"] == "mutation-substitute")
    assert stage["kind"] == "subworkflow"
    assert stage["workflow"]["workflow_id"] == "tst.diff-scoped-mutation-gate"
    assert stage["isolation"] == "worktree", "a mutating child must not share this tree's index"
    assert stage["propagate_failure"] is True
    ctx = kit.worked_context(d)
    assert _expr.evaluate(stage["when"], ctx, strict=True) is False, (
        "the worked example has no pure additions, so the substitute must not run"
    )
    assert _expr.evaluate(stage["when"], {**ctx, "pure_addition_count": 2}, strict=True) is True


def test_the_subworkflow_reference_resolves_to_a_real_sibling_blueprint() -> None:
    """DSL-SEM-006 checks the declaration; this checks the file actually exists on disk."""
    d = doc()
    declared = d["subworkflows"]["tst.diff-scoped-mutation-gate"]
    assert declared["workflow_id"] == "tst.diff-scoped-mutation-gate"
    target = kit.WORKFLOW_DIR / "tst.diff-scoped-mutation-gate.json"
    assert target.is_file(), f"the declared child workflow is not on disk: {target}"
    assert declared["source"] == "platform/workflows/tst.diff-scoped-mutation-gate.json"
    assert kit.load("tst.diff-scoped-mutation-gate")["id"] == declared["workflow_id"]


def test_the_aggregate_cannot_be_better_than_the_worst_per_test_outcome() -> None:
    d = doc()
    unit = next(u for s in d["stages"] if s["id"] == "certify-or-refuse" for u in [s["work_unit"]])
    assert "no better than the worst" in unit["completion_sentinel"] or "worst per-test" in unit["question_or_target"]
    assert any("REFUSED" in t for t in unit["tests_required"])


def test_it_is_fully_deterministic_given_the_refs() -> None:
    d = doc()
    assert d["replay"]["deterministic"] is True
    assert d["replay"]["verify"] == "hash-equal"
    assert d["estimate"]["confidence"] == "almost-certain"
    assert d["roles"]["certifier"]["authority"] == "judge"


def test_MUTATION_weakening_the_red_before_gate_removes_its_power() -> None:
    d = doc()
    bad = {"tests_passing_at_pre_change_ref": 2}
    assert kit.evaluate_gate(d, "red-before", bad) is False

    weakened = kit.mutated(d)
    weakened["gates"]["red-before"]["expression"] = "claimed_tests >= 1"
    ctx = kit.worked_context(weakened)
    ctx.update(bad)
    assert _expr.evaluate(weakened["gates"]["red-before"]["expression"], ctx, strict=True) is True


def test_MUTATION_dropping_the_red_before_gate_is_rejected() -> None:
    kit.assert_rejected(kit.drop_stage(doc(), "red-before"), "red-before gate removed")


def test_MUTATION_an_undeclared_subworkflow_reference_is_rejected() -> None:
    """DSL-SEM-006: a child workflow that is referenced but not declared can never be resolved."""
    d = kit.mutated(doc())
    del d["subworkflows"]["tst.diff-scoped-mutation-gate"]
    kit.assert_rejected(d, "subworkflow referenced but not declared")
