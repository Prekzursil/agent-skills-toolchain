"""End-to-end test for FLAGSHIP blueprint BP-TST-02 (card 55), tst.diff-scoped-mutation-gate.

Mechanism protected: mutants stay INSIDE the diff, an unstable mutant is INDETERMINATE and never
killed, a survivor is reported as a test gap, and coverage may not be presented as protection.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bp5_testkit as kit  # noqa: E402
from wfdsl import expr as _expr  # noqa: E402

SLUG = "tst.diff-scoped-mutation-gate"


def doc() -> dict:
    return kit.load(SLUG)


def test_validates_on_disk() -> None:
    kit.assert_accepted(doc())


def test_whole_repo_mutation_is_refused_before_any_mutant_runs() -> None:
    d = doc()
    kit.assert_precedes(d, "bounded-to-the-diff", "run-mutants")
    assert d["gates"]["bounded-to-the-diff"]["on_fail"] == "fail"
    assert kit.evaluate_gate(d, "bounded-to-the-diff") is True
    assert kit.evaluate_gate(d, "bounded-to-the-diff", {"mutants_outside_diff": 1}) is False
    assert kit.evaluate_gate(d, "bounded-to-the-diff", {"mutants_generated": 999}) is False


def test_the_default_argument_operator_that_caught_the_measured_hole_is_present() -> None:
    """The recorded case: reverting a default from 1024 to 512 still passed 15/15 because every
    test passed the value explicitly. Without this operator the gate cannot see that class."""
    d = doc()
    ops = d["params"]["mutation_operators"]["default"]
    assert "default-argument-change" in ops, "the operator that found the measured hole is missing"
    assert d["params"]["mutation_operators"]["min_items"] >= 1


def test_an_unstable_mutant_is_indeterminate_not_killed() -> None:
    d = doc()
    assert kit.evaluate_gate(d, "indeterminate-not-killed") is True
    assert (
        kit.evaluate_gate(d, "indeterminate-not-killed", {"unstable_mutants_reported_as_killed": 1})
        is False
    ), "counting a flaky mutant as killed inflates the score and hides a gap"
    assert d["params"]["flake_reruns"]["minimum"] >= 1


def test_the_flake_repair_loop_has_an_independent_verify() -> None:
    d = doc()
    rl = next(s for s in d["stages"] if s["id"] == "reclassify-flakes")
    assert rl["kind"] == "repair_loop"
    assert rl["classification_filter"] == ["runner-flake"], "the loop must not absorb real failures"
    assert rl["verify"]["kind"] == "gate"
    assert rl["verify"]["gate"]["on_fail"] == "fail"


def test_coverage_may_not_be_presented_as_protection() -> None:
    d = doc()
    assert kit.evaluate_gate(d, "coverage-is-not-protection") is True
    assert (
        kit.evaluate_gate(d, "coverage-is-not-protection", {"coverage_used_as_protection_claim": True})
        is False
    )
    assert (
        kit.evaluate_gate(d, "coverage-is-not-protection", {"surviving_mutants_reported_as_gaps": False})
        is False
    ), "a survivor that is not reported as a gap is a silently swallowed test hole"


def test_no_mutated_source_may_survive_the_run() -> None:
    """A leaked mutant in the working tree is a real hazard, not a cosmetic one."""
    d = doc()
    gate = d["gates"]["mutation-source-restored"]
    assert gate["on_fail"] == "escalate-to-human"
    assert kit.evaluate_gate(d, "mutation-source-restored") is True
    assert kit.evaluate_gate(d, "mutation-source-restored", {"working_tree_clean_after_run": False}) is False
    assert "platform/lib/**" in d["tool_policy"]["forbid_write_paths"]


def test_the_survival_rate_is_labelled_diff_scoped_not_repository_wide() -> None:
    d = doc()
    unit = next(u for s in d["stages"] if s["id"] == "report-survivors" for u in [s["work_unit"]])
    assert "diff-scoped" in unit["question_or_target"]
    assert "not a repository mutation score" in unit["question_or_target"] or "must not be presented" in unit["question_or_target"]
    assert "overclaim" in unit["failure_classification"]


def test_equivalent_mutant_triage_is_a_separate_voting_role() -> None:
    """Equivalent mutants are the known noise source; a filter would hide them."""
    d = doc()
    assert d["roles"]["survivor-triager"]["authority"] == "voting"
    assert d["roles"]["survivor-triager"]["effort"] == "high"
    assert d["roles"]["mutant-runner"]["effort"] == "low", "the run loop is mechanical"


def test_MUTATION_weakening_the_diff_bound_removes_its_power() -> None:
    d = doc()
    bad = {"mutants_outside_diff": 5}
    assert kit.evaluate_gate(d, "bounded-to-the-diff", bad) is False

    weakened = kit.mutated(d)
    weakened["gates"]["bounded-to-the-diff"]["expression"] = "mutants_generated <= max_mutants"
    ctx = kit.worked_context(weakened)
    ctx.update(bad)
    assert _expr.evaluate(weakened["gates"]["bounded-to-the-diff"]["expression"], ctx, strict=True) is True


def test_MUTATION_dropping_the_indeterminate_gate_is_rejected() -> None:
    kit.assert_rejected(kit.drop_stage(doc(), "indeterminate-not-killed"), "indeterminate gate removed")


def test_MUTATION_unbounding_the_mutant_fanout_is_rejected() -> None:
    d = kit.mutated(doc())
    stage = next(s for s in d["stages"] if s["id"] == "run-mutants")
    del stage["max_concurrency"]
    kit.assert_rejected(d, "one test run per mutant with unbounded concurrency")


def test_MUTATION_a_repair_loop_without_a_verify_is_rejected() -> None:
    """A repair loop with no independent verify is a retry that reports success."""
    d = kit.mutated(doc())
    rl = next(s for s in d["stages"] if s["id"] == "reclassify-flakes")
    del rl["verify"]
    kit.assert_rejected(d, "repair loop with no verify stage")
