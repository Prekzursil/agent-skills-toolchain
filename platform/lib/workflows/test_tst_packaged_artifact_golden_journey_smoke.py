"""End-to-end test for FLAGSHIP blueprint BP-TST-05 (card 58),
tst.packaged-artifact-golden-journey-smoke.

Mechanism protected: the postcondition must MEASURE the produced artifact. "It did not crash" is
refused, and a green source tree is not evidence for any journey.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bp5_testkit as kit  # noqa: E402
from wfdsl import expr as _expr  # noqa: E402

SLUG = "tst.packaged-artifact-golden-journey-smoke"


def doc() -> dict:
    return kit.load(SLUG)


def test_validates_on_disk() -> None:
    kit.assert_accepted(doc())


def test_absence_of_a_crash_is_refused_as_a_postcondition() -> None:
    d = doc()
    assert d["gates"]["postcondition-is-a-measurement"]["on_fail"] == "fail"
    assert kit.evaluate_gate(d, "postcondition-is-a-measurement") is True
    assert (
        kit.evaluate_gate(d, "postcondition-is-a-measurement", {"probes_asserting_only_absence_of_crash": 1})
        is False
    )
    assert (
        kit.evaluate_gate(d, "postcondition-is-a-measurement", {"probes_measuring_produced_artifact": 0})
        is False
    ), "zero measurements means the smoke measured nothing about the output"


def test_a_green_source_tree_is_not_evidence_for_a_journey() -> None:
    d = doc()
    assert kit.evaluate_gate(d, "source-green-not-evidence") is True
    assert (
        kit.evaluate_gate(d, "source-green-not-evidence", {"source_tree_green_used_as_journey_evidence": True})
        is False
    )


def test_the_launch_stage_fails_fast_because_it_is_the_highest_value_failure() -> None:
    """The card: an artifact that will not launch is the exact class a green CI hides."""
    d = doc()
    stage = next(s for s in d["stages"] if s["id"] == "install-or-launch")
    assert stage["on_failure"]["on_failure"] == "fail-fast"
    assert "missing-runtime-dependency" in stage["on_failure"]["classify_as"]
    assert stage["retry"]["strategy"] == "none", (
        "retrying an install in the SAME environment is not a second signal"
    )


def test_the_clean_environment_is_recorded_not_assumed() -> None:
    d = doc()
    assert kit.evaluate_gate(d, "clean-environment") is True
    assert kit.evaluate_gate(d, "clean-environment", {"ambient_dependency_leakage_checked": False}) is False
    assert kit.evaluate_gate(d, "clean-environment", {"env_kind_recorded": False}) is False
    assert set(d["params"]["clean_env"]["enum"]) >= {"fresh-venv", "container"}


def test_journeys_run_serially_so_one_journey_cannot_pollute_another() -> None:
    d = doc()
    stage = next(s for s in d["stages"] if s["id"] == "run-journeys")
    assert stage["max_concurrency"] == 1, "parallel journeys against one artifact share state"
    assert stage["on_item_failure"] == "continue", "a failed journey must not hide its siblings"
    assert stage["barrier"]["verify_artifact_exists"] is True


def test_every_declared_journey_must_be_attempted() -> None:
    d = doc()
    assert kit.evaluate_gate(d, "every-journey-attempted") is True
    assert kit.evaluate_gate(d, "every-journey-attempted", {"journeys_attempted": 1}) is False


def test_the_probe_role_can_veto_a_non_measurement() -> None:
    d = doc()
    assert d["roles"]["postcondition-prober"]["authority"] == "veto"
    assert "Bash:ffprobe" in d["roles"]["postcondition-prober"]["tool_permissions"]
    unit = next(u for s in d["stages"] if s["id"] == "probe-produced-artifacts" for u in [s["work_unit"]])
    assert "1080x1920" in " ".join(unit["tests_required"]), "the Reframe precedent measurement is missing"
    assert any("REFUSED" in t for t in unit["tests_required"])


def test_the_removed_dependency_both_states_control_is_declared() -> None:
    """The control that proves the smoke can SEE a packaging gap at all."""
    d = doc()
    names = {b["name"] for b in d["x_extensions"]["benchmark_cases"]}
    assert "removed-runtime-dependency" in names
    unit = next(u for s in d["stages"] if s["id"] == "install-or-launch" for u in [s["work_unit"]])
    assert any("MUST fail" in t for t in unit["tests_required"])


def test_MUTATION_weakening_the_measurement_gate_removes_its_power() -> None:
    d = doc()
    bad = {"probes_asserting_only_absence_of_crash": 3, "probes_measuring_produced_artifact": 0}
    assert kit.evaluate_gate(d, "postcondition-is-a-measurement", bad) is False

    weakened = kit.mutated(d)
    weakened["gates"]["postcondition-is-a-measurement"]["expression"] = "journeys_attempted >= 1"
    ctx = kit.worked_context(weakened)
    ctx.update(bad)
    assert _expr.evaluate(
        weakened["gates"]["postcondition-is-a-measurement"]["expression"], ctx, strict=True
    ) is True


def test_MUTATION_dropping_the_measurement_gate_is_rejected() -> None:
    kit.assert_rejected(
        kit.drop_stage(doc(), "postcondition-is-a-measurement"), "postcondition gate removed"
    )


def test_MUTATION_journey_fanout_without_a_barrier_partial_policy_is_rejected() -> None:
    d = kit.mutated(doc())
    stage = next(s for s in d["stages"] if s["id"] == "run-journeys")
    del stage["barrier"]["on_partial"]
    kit.assert_rejected(d, "journey barrier that silently drops a straggler")
