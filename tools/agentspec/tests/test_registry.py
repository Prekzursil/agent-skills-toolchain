"""The hermetic eval registry: R1-R6 and R8, executable, against the fake rail."""

from __future__ import annotations

import dataclasses

import pytest

from agentspec.envelope import validate_observation
from agentspec.evals.impl import DEFAULT_IMPL
from agentspec.evals.registry import (
    REGISTRY,
    EvalOutcome,
    EvalRow,
    row_ids,
    rows,
    run_all,
    run_row,
    summary,
)

EXPECTED_IDS = ("R1", "R2", "R3", "R4", "R5", "R6", "R8")


def test_the_registry_holds_exactly_the_declared_regression_rows() -> None:
    assert row_ids() == EXPECTED_IDS


def test_every_row_declares_its_measured_failure_and_red_condition() -> None:
    """A row without a stated RED condition is a checklist item, not an eval."""
    for row in REGISTRY:
        assert row.kind == "regression", row.id
        assert row.title.strip(), row.id
        assert len(row.measured_failure) > 30, row.id
        assert len(row.red_condition) > 30, row.id


def test_no_row_is_stubbed_skipped_or_xfailed() -> None:
    for row in REGISTRY:
        assert callable(row.run), row.id


def test_every_row_passes_against_the_default_implementation() -> None:
    outcomes = run_all()
    assert [o.row_id for o in outcomes] == list(EXPECTED_IDS)
    failed = [(o.row_id, o.detail) for o in outcomes if not o.passed]
    assert failed == []


def test_each_outcome_carries_a_valid_observation_envelope() -> None:
    for outcome in run_all():
        assert outcome.observation.status == "success"
        assert validate_observation(outcome.observation) == ()


def test_run_row_returns_an_error_envelope_when_a_row_fails() -> None:
    broken = EvalRow(
        id="RX",
        kind="regression",
        title="a row that fails",
        measured_failure="x" * 40,
        red_condition="y" * 40,
        run=lambda _impl: (False, "deliberately failed"),
    )
    outcome = run_row(broken)
    assert outcome.passed is False
    assert outcome.observation.status == "error"
    assert outcome.observation.error is not None
    assert outcome.observation.error.code == "policy-violation"
    assert outcome.observation.error.root_cause
    assert outcome.observation.error.retry_instruction
    assert outcome.observation.error.stop_condition
    assert validate_observation(outcome.observation) == ()


def test_a_row_that_raises_is_reported_as_failed_not_propagated() -> None:
    """An eval harness must always reach a terminal state."""

    def boom(_impl: object) -> tuple[bool, str]:
        raise RuntimeError("kaboom")

    outcome = run_row(
        EvalRow(
            id="RY",
            kind="regression",
            title="a row that raises",
            measured_failure="x" * 40,
            red_condition="y" * 40,
            run=boom,
        )
    )
    assert outcome.passed is False
    assert "kaboom" in outcome.detail


# --- the live lane is opt-in and excluded by default ---------------------------------------

LIVE_ROW = EvalRow(
    id="L1",
    kind="regression",
    title="a live-rail row",
    measured_failure="x" * 40,
    red_condition="y" * 40,
    run=lambda _impl: (True, "would need a real rail"),
    live=True,
)


def test_the_shipped_registry_contains_no_live_row() -> None:
    """This package ships no live rail, so CI is hermetic by construction."""
    assert [r.id for r in REGISTRY if r.live] == []


def test_a_live_row_is_excluded_by_default() -> None:
    catalog = (*REGISTRY, LIVE_ROW)
    assert "L1" not in [r.id for r in rows(catalog=catalog)]


def test_a_live_row_is_included_only_when_explicitly_asked_for() -> None:
    catalog = (*REGISTRY, LIVE_ROW)
    assert "L1" in [r.id for r in rows(catalog=catalog, include_live=True)]


def test_run_all_honours_the_live_filter_in_both_directions() -> None:
    catalog = (*REGISTRY, LIVE_ROW)
    assert "L1" not in [o.row_id for o in run_all(catalog=catalog)]
    assert "L1" in [o.row_id for o in run_all(catalog=catalog, include_live=True)]


def test_row_ids_honours_the_live_filter() -> None:
    catalog = (*REGISTRY, LIVE_ROW)
    assert row_ids(catalog=catalog, include_live=True)[-1] == "L1"


# --- the summary envelope -----------------------------------------------------------------


def test_summary_of_an_all_green_run_is_success() -> None:
    obs = summary(run_all())
    assert obs.status == "success"
    assert "7/7" in obs.summary
    assert validate_observation(obs) == ()


def test_summary_of_a_run_with_a_failure_is_an_error_naming_the_row() -> None:
    outcomes = (
        *run_all(),
        EvalOutcome(
            row_id="RX",
            passed=False,
            detail="nope",
            observation=run_row(
                EvalRow(
                    id="RX",
                    kind="regression",
                    title="t",
                    measured_failure="x" * 40,
                    red_condition="y" * 40,
                    run=lambda _impl: (False, "nope"),
                )
            ).observation,
        ),
    )
    obs = summary(outcomes)
    assert obs.status == "error"
    assert "RX" in obs.summary
    assert validate_observation(obs) == ()


def test_summary_of_an_empty_run_is_a_warning_not_a_silent_pass() -> None:
    """Zero rows executed is a DETECTOR failure, never a green run."""
    obs = summary(())
    assert obs.status == "warning"
    assert validate_observation(obs) == ()


def test_registry_records_are_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        REGISTRY[0].id = "x"  # type: ignore[misc]


def test_the_default_impl_exposes_every_injected_seam() -> None:
    """The mutation guard swaps these; a missing seam means an unprotected rule."""
    assert sorted(f.name for f in dataclasses.fields(DEFAULT_IMPL)) == [
        "build_argv",
        "build_for_rail",
        "check_dispatch",
        "classify",
        "judge",
        "plan_retry",
        "scan_source",
        "serialise",
        "terminal_line",
    ]
