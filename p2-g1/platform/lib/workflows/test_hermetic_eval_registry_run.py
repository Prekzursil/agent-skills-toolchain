"""End-to-end tests for blueprint 76, BP-DAT-05 hermetic-eval-registry-run (FLAGSHIP).

Two properties carry this blueprint and both are anti-overclaim devices:
  * a delta smaller than the measured re-run variance band is NOT a delta, and
  * a deliberately degraded config must score lower, or the eval is not protecting anything.
Each is tested against the real document and against a mutation that removes exactly that
guarantee, using the same predicate in both arms.
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

BP = "hermetic-eval-registry-run"


def test_document_is_schema_valid_and_semantically_clean() -> None:
    doc = K.load(BP)
    errs = list(schemas.workflow_validator().iter_errors(doc))
    assert errs == [], [
        f"{'/'.join(str(p) for p in e.absolute_path)} [{e.validator}]" for e in errs[:5]
    ]
    assert [r.to_json() for r in semantics.check_workflow(doc) if r.violations] == []


def test_every_inline_work_unit_passes_the_strict_profile() -> None:
    validator = schemas.work_unit_validator("strict")
    units = C.work_units(K.load(BP))
    assert len(units) == 6
    assert {u["id"] for u in units if list(validator.iter_errors(u))} == set()


# --------------------------------- property 1: the delta must clear the variance band


def test_delta_is_gated_on_the_variance_band_and_the_degraded_control() -> None:
    result = C.delta_gated_on_variance_and_degraded_control(K.load(BP))
    assert result.ok, result.why()


def test_control_dropping_the_degraded_control_condition_is_caught() -> None:
    """Both-states control: without the degraded-control condition an eval that cannot see ANY
    regression could still report an improvement. That is a green suite protecting nothing."""
    mutated = K.mutate(
        K.load(BP),
        K.weaken_gate(
            "delta-exceeds-variance", "delta_vs_baseline > rerun_variance_band"
        ),
    )
    K.assert_still_schema_valid(mutated)
    result = C.delta_gated_on_variance_and_degraded_control(mutated)
    assert not result.ok, (
        "the predicate accepted a delta gate with no sensitivity control"
    )
    assert any("degraded_control_scored_lower" in r for r in result.reasons), (
        result.reasons
    )


def test_control_dropping_the_variance_band_condition_is_caught() -> None:
    """Both-states control: without the band, a +1.2 point movement inside +/-2.0 points of noise
    would be reported as an improvement."""
    mutated = K.mutate(
        K.load(BP),
        K.weaken_gate(
            "delta-exceeds-variance",
            "delta_vs_baseline > 0 AND degraded_control_scored_lower == true",
        ),
    )
    K.assert_still_schema_valid(mutated)
    result = C.delta_gated_on_variance_and_degraded_control(mutated)
    assert not result.ok, (
        "the predicate accepted a delta gate with no variance threshold"
    )
    assert any("rerun_variance_band" in r for r in result.reasons), result.reasons


def test_control_letting_the_comparison_run_without_the_degraded_arm_is_caught() -> (
    None
):
    mutated = K.mutate(
        K.load(BP), K.drop_dependency("compare-to-baseline", "degraded-control")
    )
    K.assert_still_schema_valid(mutated)
    result = C.delta_gated_on_variance_and_degraded_control(mutated)
    assert not result.ok, "the comparison could run before the sensitivity arm"
    assert any("does not depend on 'degraded-control'" in r for r in result.reasons), (
        result.reasons
    )


# ----------------------------------------------------- property 2: the run is hermetic


def test_the_run_is_hermetic() -> None:
    result = C.run_is_hermetic(K.load(BP))
    assert result.ok, result.why()


def test_control_permitting_unseeded_randomness_in_replay_is_caught() -> None:
    """Both-states control: hermeticity is the precondition that makes the band readable. Allow
    entropy back in and the band measures the entropy, not the harness."""
    mutated = K.mutate(K.load(BP), K.drop_replay_forbidden_source("random"))
    K.assert_still_schema_valid(mutated)
    result = C.run_is_hermetic(mutated)
    assert not result.ok, (
        "the predicate accepted a replay policy that permits unseeded entropy"
    )
    assert any("'random'" in r for r in result.reasons), result.reasons


def test_control_weakening_the_hermeticity_gate_is_caught() -> None:
    mutated = K.mutate(K.load(BP), K.weaken_gate("hermetic", "wall_clock_reads == 0"))
    K.assert_still_schema_valid(mutated)
    result = C.run_is_hermetic(mutated)
    assert not result.ok, "a hermeticity gate that only counts clock reads was accepted"
    assert any("unseeded_entropy_reads" in r for r in result.reasons), result.reasons


# ------------------------------------------- property 3: both arms, matched case hashes


def test_both_arms_are_barriered_before_any_comparison() -> None:
    doc = K.load(BP)
    join = C.stage(doc, "arms-join")
    assert join is not None and join["kind"] == "barrier"
    assert join["barrier"]["mode"] == "all"
    assert join["barrier"]["on_partial"] == "fail"
    assert set(join["barrier"]["require_stages"]) == {"run-under-test", "run-baseline"}
    assert "arms-join" in C.ancestors(doc, "compare-to-baseline")


def test_an_eval_set_too_small_reports_not_checked_rather_than_a_pass_rate() -> None:
    doc = K.load(BP)
    ids = C.identifiers(C.gate_expression(doc, "size-gate"))
    assert {"eval_cases", "min_eval_cases"} <= ids
    pin = C.stage(doc, "pin-registry")
    assert any("NOT-CHECKED" in t for t in pin["work_unit"]["tests_required"])


def test_the_variance_loop_is_bounded_and_needs_at_least_three_runs() -> None:
    conv = C.stage(K.load(BP), "measure-variance")["convergence"]
    assert conv["min_iterations"] >= 3, "fewer than three runs is not a band"
    assert conv["max_iterations"] <= 25
    assert conv["no_progress_rounds"] >= 1


def test_the_worked_example_states_the_counterfactual_verdict() -> None:
    """A worked example that only shows the passing case does not demonstrate the band."""
    example = K.load(BP)["x_extensions"]["bp7"]["worked_example"]
    trace = " ".join(example["expected_trace"])
    assert "UNCHANGED-WITHIN-BAND" in trace, (
        "the example never shows the sub-band verdict"
    )
    assert "CAN see a regression" in trace or "can see a regression" in trace
    assert example["expected_terminal_state"].startswith("SUCCESS:DAT-76")
