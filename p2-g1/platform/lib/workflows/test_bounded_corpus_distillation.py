"""End-to-end tests for blueprint 73, BP-DAT-02 bounded-corpus-distillation (FLAGSHIP).

Every property test is paired with a MUTATION control that must make the SAME predicate go
False, and go False for the stated reason. A predicate that stays True under mutation is not
enforcing anything; a predicate that goes False for an unrelated reason is not the control it
claims to be, so each negative test also asserts the reason text.
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

BP = "bounded-corpus-distillation"


# ------------------------------------------------------------------ contract conformance


def test_document_is_schema_valid() -> None:
    doc = K.load(BP)
    errs = list(schemas.workflow_validator().iter_errors(doc))
    assert errs == [], [
        f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'} [{e.validator}] {e.message}"
        for e in errs[:5]
    ]


def test_no_semantic_violations() -> None:
    doc = K.load(BP)
    bad = [r.to_json() for r in semantics.check_workflow(doc) if r.violations]
    assert bad == [], bad


def test_every_inline_work_unit_passes_the_strict_profile() -> None:
    doc = K.load(BP)
    validator = schemas.work_unit_validator("strict")
    units = C.work_units(doc)
    assert len(units) == 5, f"expected 5 inline units, found {len(units)}"
    failures = {
        u["id"]: [
            f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}:{e.validator}"
            for e in errs
        ]
        for u in units
        if (errs := list(validator.iter_errors(u)))
    }
    assert failures == {}, failures


# ------------------------------------------------- property 1: two-probe agreement gate


def test_two_probe_agreement_gates_streaming() -> None:
    result = C.two_probe_agreement_gates_streaming(K.load(BP))
    assert result.ok, result.why()


def test_control_removing_the_agreement_gate_edge_is_caught() -> None:
    """Both-states control: if streaming no longer waits on the agreement gate, the predicate
    must fire. This is the exact failure a naive glob returning 11,335 for a 708-file population
    would have produced."""
    mutated = K.mutate(
        K.load(BP), K.drop_dependency("stream-extract", "probe-agreement")
    )
    K.assert_still_schema_valid(mutated)
    result = C.two_probe_agreement_gates_streaming(mutated)
    assert not result.ok, "the predicate stayed True with the agreement gate bypassed"
    assert any(
        "does not transitively depend on the agreement gate" in r
        for r in result.reasons
    ), result.reasons


def test_control_making_both_probes_use_one_role_is_caught() -> None:
    """Both-states control: two probes sharing a role are one instrument run twice, which is not
    a second signal. The predicate must reject it even though the graph is unchanged."""
    mutated = K.mutate(
        K.load(BP), K.set_stage_role("enumerate-independent", "enumerator")
    )
    K.assert_still_schema_valid(mutated)
    result = C.two_probe_agreement_gates_streaming(mutated)
    assert not result.ok, "the predicate accepted two probes with the same role"
    assert any("same role" in r for r in result.reasons), result.reasons


def test_control_dropping_the_count_comparison_is_caught() -> None:
    mutated = K.mutate(K.load(BP), K.weaken_gate("probes-agree", "probe_a_count >= 0"))
    K.assert_still_schema_valid(mutated)
    result = C.two_probe_agreement_gates_streaming(mutated)
    assert not result.ok, "a gate that compares nothing was accepted"
    assert any("does not compare the two probe counts" in r for r in result.reasons), (
        result.reasons
    )


# --------------------------------------------- property 2: coverage honesty accounting


def test_malformed_and_dropped_tail_are_accounted() -> None:
    result = C.malformed_and_dropped_tail_are_accounted(K.load(BP))
    assert result.ok, result.why()


def test_control_dropping_the_tail_ledger_condition_is_caught() -> None:
    """Both-states control: a silent skip is a coverage lie. Removing the dropped-tail condition
    from the gate must be detected, or the workflow could report coverage while hiding the tail."""
    mutated = K.mutate(
        K.load(BP),
        K.weaken_gate(
            "coverage-honest",
            "malformed_records_counted == true AND coverage_reported == true",
        ),
    )
    K.assert_still_schema_valid(mutated)
    result = C.malformed_and_dropped_tail_are_accounted(mutated)
    assert not result.ok, (
        "the predicate accepted a coverage gate that ignores the dropped tail"
    )
    assert any("dropped_tail_recorded" in r for r in result.reasons), result.reasons


# ------------------------------------------------------- property 3: bounded resources


def test_the_truncation_loop_is_bounded_and_has_a_no_progress_exit() -> None:
    """A loop whose only exit is a convergence expression spins forever when the metric never
    moves; the bound and the no-progress exit are the safety properties."""
    loop = C.stage(K.load(BP), "bound-to-budget")
    assert loop is not None and loop["kind"] == "loop"
    conv = loop["convergence"]
    assert 1 <= conv["max_iterations"] <= 1000, conv
    assert conv["no_progress_rounds"] >= 1, conv
    assert conv["on_no_convergence"] in ("fail", "escalate", "emit-partial"), conv
    metrics = {m["name"] for m in conv["metrics"]}
    assert "tokens_selected" in metrics


def test_fanout_concurrency_is_bounded_and_the_barrier_declares_a_partial_policy() -> (
    None
):
    fan = C.stage(K.load(BP), "stream-extract")
    assert fan is not None
    assert 1 <= fan["max_concurrency"] <= 1024, fan["max_concurrency"]
    barrier = fan["barrier"]
    assert barrier["on_partial"] == "fail", barrier
    assert barrier["verify_artifact_exists"] is True
    assert any(
        "started in the background" in p for p in barrier["reject_result_matching"]
    ), barrier


# --------------------------------------------------------- property 4: worked example


def test_the_worked_example_names_the_halt_case_not_only_the_happy_path() -> None:
    """An example that only shows success does not demonstrate the gate. The trace must show
    what happens when the two probes disagree."""
    ext = K.load(BP)["x_extensions"]["bp7"]
    example = ext["worked_example"]
    trace = " ".join(example["expected_trace"])
    assert "11335" in trace or "11,335" in trace, (
        "the example does not cite the measured probe disagreement"
    )
    assert "HALT" in trace, (
        "the example does not state what the agreement gate does on disagreement"
    )
    assert example["expected_terminal_state"].startswith("SUCCESS:DAT-73")
    assert "UNVERIFIED" in ext["unverified"]
    assert "settling experiment" in ext["unverified"].lower()
