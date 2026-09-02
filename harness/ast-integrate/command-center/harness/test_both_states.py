"""Self-test of the both-states control harness (TST-0013).

Each ``test_*`` function runs a deliberately shaped check through
``both_states.control`` and returns the resulting ``ControlRecord`` so the
named probes (and ``run_all``) can inspect verdicts; under pytest the inline
asserts make the same functions fail loudly.

Fixtures are plain dicts: a *good* receipt with a recorded test and a *broken*
receipt whose ``tests`` list is empty. A correct detector fires only on the
broken one.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from both_states import (  # noqa: E402
    FIRES,
    FIRES_IN_BOTH,
    POLARITY_INVERTED,
    REJECTED,
    SILENT,
    SILENT_IN_BOTH,
    VALID,
    BothStatesRejected,
    ControlRecord,
    both_states,
    both_states_control,
    both_states_decorator,
    control,
)

__all__ = [
    "GOOD_STATE",
    "BROKEN_STATE",
    "run_all",
    "test_harness_rejects_a_check_silent_in_both_states",
    "test_harness_rejects_a_check_that_fires_in_both_states",
    "test_harness_rejects_inverted_polarity",
    "test_harness_accepts_a_correct_check",
    "test_harness_accepts_assert_style_check",
    "test_decorator_form_accepts_correct_check",
    "test_fixture_form_raises_on_rejection",
    "test_harness_is_itself_both_states_controlled",
]

GOOD_STATE: dict[str, Any] = {
    "unit_id": "TST-0013",
    "state": "SUCCESS",
    "tests": [{"id": "test_receipt_has_a_test", "result": "PASS"}],
}
BROKEN_STATE: dict[str, Any] = {
    "unit_id": "TST-0013",
    "state": "SUCCESS",
    "tests": [],
}


def _fresh(state: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(state)


# --- detectors under test -------------------------------------------------------


def no_tests_recorded(state: dict[str, Any]) -> bool:
    """Correct detector: fires when a receipt records no tests."""
    return not state.get("tests")


def no_tests_recorded_assert_style(state: dict[str, Any]) -> None:
    """Correct detector, assert style: raises on the broken receipt."""
    assert state.get("tests"), "receipt records no tests"


def inert_check(state: dict[str, Any]) -> bool:
    """Deliberately inert: never fires, whatever the state."""
    return False


def always_fires(state: dict[str, Any]) -> bool:
    """Deliberately noisy: fires on every state."""
    return True


def inverted_check(state: dict[str, Any]) -> bool:
    """Polarity inverted: fires on the good receipt, silent on the broken one."""
    return bool(state.get("tests"))


# --- rejection paths ------------------------------------------------------------


def test_harness_rejects_a_check_silent_in_both_states() -> ControlRecord:
    rec = control(
        inert_check,
        _fresh(GOOD_STATE),
        _fresh(BROKEN_STATE),
        check_id="inert_check",
        description="A check silent in both states measures nothing.",
    )
    assert rec.verdict == REJECTED, rec.to_dict()
    assert rec.rejection_reason == SILENT_IN_BOTH, rec.to_dict()
    assert rec.good_outcome == SILENT and rec.broken_outcome == SILENT
    assert rec.silent_on_good_state is True and rec.fired_on_bad_state is False
    return rec


def test_harness_rejects_a_check_that_fires_in_both_states() -> ControlRecord:
    rec = control(
        always_fires,
        _fresh(GOOD_STATE),
        _fresh(BROKEN_STATE),
        check_id="always_fires",
        description="A check that fires in both states is a false-positive machine.",
    )
    assert rec.verdict == REJECTED, rec.to_dict()
    assert rec.rejection_reason == FIRES_IN_BOTH, rec.to_dict()
    assert rec.good_outcome == FIRES and rec.broken_outcome == FIRES
    assert rec.silent_on_good_state is False and rec.fired_on_bad_state is True
    return rec


def test_harness_rejects_inverted_polarity() -> ControlRecord:
    rec = control(
        inverted_check,
        _fresh(GOOD_STATE),
        _fresh(BROKEN_STATE),
        check_id="inverted_check",
        description="A check that fires on good and is silent on broken has inverted polarity.",
    )
    assert rec.verdict == REJECTED, rec.to_dict()
    assert rec.rejection_reason == POLARITY_INVERTED, rec.to_dict()
    assert rec.good_outcome == FIRES and rec.broken_outcome == SILENT
    return rec


# --- accept paths ---------------------------------------------------------------


def test_harness_accepts_a_correct_check() -> ControlRecord:
    rec = control(
        no_tests_recorded,
        _fresh(GOOD_STATE),
        _fresh(BROKEN_STATE),
        check_id="no_tests_recorded",
        description="Fires only when the receipt records no tests.",
    )
    assert rec.verdict == VALID, rec.to_dict()
    assert rec.rejection_reason is None
    assert rec.good_outcome == SILENT and rec.broken_outcome == FIRES
    assert rec.silent_on_good_state is True and rec.fired_on_bad_state is True
    assert rec.to_dict()["check_id"] == "no_tests_recorded"
    return rec


def test_harness_accepts_assert_style_check() -> ControlRecord:
    rec = both_states_control(
        no_tests_recorded_assert_style,
        _fresh(GOOD_STATE),
        _fresh(BROKEN_STATE),
        check_id="no_tests_recorded_assert_style",
        description="Assert-style detector: AssertionError on the broken receipt counts as FIRES.",
    )
    assert rec.verdict == VALID, rec.to_dict()
    assert rec.broken_detail is not None and "AssertionError" in rec.broken_detail
    return rec


def test_decorator_form_accepts_correct_check() -> ControlRecord:
    @both_states_decorator(
        _fresh(GOOD_STATE),
        _fresh(BROKEN_STATE),
        description="Decorator form of the same correct detector.",
    )
    def decorated_no_tests_recorded(state: dict[str, Any]) -> bool:
        return not state.get("tests")

    rec = decorated_no_tests_recorded()
    assert isinstance(rec, ControlRecord)
    assert rec.verdict == VALID, rec.to_dict()
    assert rec.check_id.endswith("decorated_no_tests_recorded"), rec.check_id
    assert decorated_no_tests_recorded.check(_fresh(BROKEN_STATE)) is True  # type: ignore[attr-defined]
    assert decorated_no_tests_recorded.assert_valid().verdict == VALID  # type: ignore[attr-defined]
    return rec


def test_fixture_form_raises_on_rejection() -> ControlRecord:
    pair = both_states(_fresh(GOOD_STATE), _fresh(BROKEN_STATE))
    accepted = pair.assert_valid(no_tests_recorded, check_id="fixture_no_tests_recorded")
    assert accepted.verdict == VALID
    try:
        pair.assert_valid(inert_check, check_id="fixture_inert_check")
    except BothStatesRejected as exc:
        assert exc.record.rejection_reason == SILENT_IN_BOTH
    else:  # pragma: no cover - the harness must refuse an inert check
        raise AssertionError("fixture form accepted an inert check")
    return accepted


# --- the harness controlling itself ---------------------------------------------


def test_harness_is_itself_both_states_controlled() -> ControlRecord:
    """The harness is SILENT (accepts) on a correct check and FIRES (rejects) on an inert one."""

    def harness_rejects(candidate_check: Any) -> bool:
        rec = control(candidate_check, _fresh(GOOD_STATE), _fresh(BROKEN_STATE))
        return rec.verdict == REJECTED

    rec = control(
        harness_rejects,
        no_tests_recorded,  # good state: a correct check -> harness accepts (SILENT)
        inert_check,  # broken state: an inert check -> harness rejects (FIRES)
        check_id="harness_self_control",
        description=(
            "The harness applied to itself: silent on a correct detector, "
            "fires on a deliberately inert one."
        ),
    )
    assert rec.verdict == VALID, rec.to_dict()
    assert rec.fired_on_bad_state is True and rec.silent_on_good_state is True
    return rec


def run_all() -> dict[str, ControlRecord]:
    """Run every self-test and return the records keyed by scenario."""
    return {
        "silent_in_both": test_harness_rejects_a_check_silent_in_both_states(),
        "fires_in_both": test_harness_rejects_a_check_that_fires_in_both_states(),
        "polarity": test_harness_rejects_inverted_polarity(),
        "correct": test_harness_accepts_a_correct_check(),
        "assert_style": test_harness_accepts_assert_style_check(),
        "decorator": test_decorator_form_accepts_correct_check(),
        "fixture": test_fixture_form_raises_on_rejection(),
        "self_control": test_harness_is_itself_both_states_controlled(),
    }


if __name__ == "__main__":
    for name, record in run_all().items():
        print(f"{name}: {record.verdict} {record.rejection_reason or ''}".rstrip())
