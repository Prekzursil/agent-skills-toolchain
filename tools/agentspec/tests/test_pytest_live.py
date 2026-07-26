"""The opt-in live lane: a `live`-marked test is DESELECTED unless --run-live is passed.

Measured hole this closes: the blocking coverage step runs a bare `pytest` with no `-m` filter,
and no pre-existing package registers a marker or a default deselect — so a `pytest.mark.live`
test would be COLLECTED AND RUN in CI. The decision lives here as a pure function so it sits
inside the coverage-gated package; tests/conftest.py is a thin shim that calls it.
"""

from __future__ import annotations

import pytest

from agentspec.evals.pytest_live import (
    LIVE_MARKER,
    MARKER_SPEC,
    RUN_LIVE_FLAG,
    deselect_reason,
    should_deselect,
)


def test_the_marker_name_and_flag_are_the_declared_pair() -> None:
    assert LIVE_MARKER == "live"
    assert RUN_LIVE_FLAG == "--run-live"


def test_the_marker_spec_is_registerable_and_self_describing() -> None:
    assert MARKER_SPEC.startswith("live:")
    assert RUN_LIVE_FLAG in MARKER_SPEC


def test_a_live_test_is_deselected_by_default() -> None:
    assert should_deselect(has_live_marker=True, run_live=False) is True


def test_a_live_test_runs_when_the_flag_is_given() -> None:
    assert should_deselect(has_live_marker=True, run_live=True) is False


def test_a_hermetic_test_is_never_deselected() -> None:
    assert should_deselect(has_live_marker=False, run_live=False) is False
    assert should_deselect(has_live_marker=False, run_live=True) is False


def test_the_deselect_reason_names_the_flag_that_would_enable_it() -> None:
    """A skip whose reason does not say how to run it is an unactionable dead end."""
    reason = deselect_reason()
    assert RUN_LIVE_FLAG in reason
    assert "live" in reason


@pytest.mark.live
def test_a_live_sentinel_exists_and_is_deselected_in_the_gate() -> None:
    """SENTINEL. If this ever executes in CI the deselect mechanism has broken.

    It deliberately asserts only things already covered by hermetic tests, so the coverage
    gate still reaches 100% with this test deselected.
    """
    from agentspec.evals.registry import row_ids

    assert row_ids()[0] == "R1"
