"""Tests for ``monitorcore.stall`` — the two-signal stall/blocked classifier and the
corroboration table (WU6), 100% line+branch.

The cardinal rule pinned here: a stall is an INFERENCE that needs TWO mechanically
independent signals (file mtime staleness AND a content-freeze across >= 2 polls); it is
never rendered red on one signal, and never on one signal at all. An abort is a FACT and
is the only condition that reaches red.
"""

from __future__ import annotations

import pytest

from monitorcore.stall import (
    CORROBORATION,
    Condition,
    Corroboration,
    StallSignals,
    StallTracker,
    classify_condition,
    corroboration_for,
    is_corroborated_stall,
    should_render_red,
)

_BOTH = StallSignals(mtime_stale=True, frozen_polls=2)


# ───────────────────────────── is_corroborated_stall ─────────────────────────────
@pytest.mark.parametrize(
    ("mtime_stale", "frozen_polls", "expected"),
    [
        (True, 2, True),  # both signals agree → corroborated
        (True, 1, False),  # content not frozen long enough → single signal
        (False, 5, False),  # mtime fresh → single signal (short-circuits)
        (False, 0, False),
    ],
)
def test_is_corroborated_stall_needs_both_signals(
    mtime_stale: bool, frozen_polls: int, expected: bool
) -> None:
    sig = StallSignals(mtime_stale=mtime_stale, frozen_polls=frozen_polls)
    assert is_corroborated_stall(sig) is expected


def test_is_corroborated_stall_honours_custom_min_polls() -> None:
    assert is_corroborated_stall(StallSignals(True, 3), min_polls=3) is True
    assert is_corroborated_stall(StallSignals(True, 2), min_polls=3) is False


# ───────────────────────────── classify_condition ─────────────────────────────
def test_classify_aborted_is_a_fact_and_outranks_everything() -> None:
    # even with both stall signals present, an aborted unit classifies as ABORTED
    cond = classify_condition(aborted=True, blocked=True, active=True, signals=_BOTH)
    assert cond is Condition.ABORTED


def test_classify_corroborated_stall_outranks_blocked() -> None:
    cond = classify_condition(aborted=False, blocked=True, active=True, signals=_BOTH)
    assert cond is Condition.STALLED


def test_classify_single_signal_is_not_a_stall() -> None:
    # mtime stale but content still moving → NOT a stall (blocked here since blocked=True)
    cond = classify_condition(
        aborted=False,
        blocked=True,
        active=False,
        signals=StallSignals(mtime_stale=True, frozen_polls=1),
    )
    assert cond is Condition.BLOCKED


def test_classify_active_when_no_freeze_no_block() -> None:
    cond = classify_condition(
        aborted=False,
        blocked=False,
        active=True,
        signals=StallSignals(mtime_stale=False, frozen_polls=0),
    )
    assert cond is Condition.ACTIVE


def test_classify_idle_is_the_floor() -> None:
    cond = classify_condition(
        aborted=False,
        blocked=False,
        active=False,
        signals=StallSignals(mtime_stale=False, frozen_polls=0),
    )
    assert cond is Condition.IDLE


# ───────────────────────────── corroboration table ─────────────────────────────
def test_corroboration_table_covers_every_condition() -> None:
    assert set(CORROBORATION) == set(Condition)
    for cond, row in CORROBORATION.items():
        assert isinstance(row, Corroboration)
        assert row.condition is cond


def test_corroboration_for_returns_the_row() -> None:
    row = corroboration_for(Condition.STALLED)
    assert (row.kind, row.severity, row.corroborates) == ("inference", "amber", True)


def test_aborted_row_is_a_fact_that_needs_no_corroboration() -> None:
    row = corroboration_for(Condition.ABORTED)
    assert (row.kind, row.severity, row.corroborates) == ("fact", "red", False)


# ───────────────────────────── should_render_red ─────────────────────────────
@pytest.mark.parametrize(
    ("condition", "red"),
    [
        (Condition.ABORTED, True),
        (Condition.STALLED, False),  # inference — amber, never red
        (Condition.BLOCKED, False),
        (Condition.ACTIVE, False),
        (Condition.IDLE, False),
    ],
)
def test_should_render_red_only_for_the_fact(condition: Condition, red: bool) -> None:
    assert should_render_red(condition) is red


def test_no_single_signal_input_can_ever_reach_red() -> None:
    """Property: across every single-signal (uncorroborated) input, red never fires."""
    for mtime_stale in (True, False):
        for frozen_polls in range(0, 4):
            sig = StallSignals(mtime_stale=mtime_stale, frozen_polls=frozen_polls)
            # a non-aborted unit can never be red, regardless of the stall signals
            cond = classify_condition(
                aborted=False, blocked=True, active=True, signals=sig
            )
            assert should_render_red(cond) is False


# ───────────────────────────── StallTracker ─────────────────────────────
def test_tracker_counts_consecutive_unchanged_polls() -> None:
    tr = StallTracker()
    assert tr.observe("a", (1, 2)) == 1  # first sight
    assert tr.observe("a", (1, 2)) == 2  # unchanged → frozen for 2 polls
    assert tr.observe("a", (1, 2)) == 3
    assert tr.observe("a", (9, 9)) == 1  # fingerprint changed → reset


def test_tracker_is_per_key() -> None:
    tr = StallTracker()
    assert tr.observe("a", 1) == 1
    assert tr.observe("b", 1) == 1  # a different key starts fresh
    assert tr.observe("a", 1) == 2


def test_tracker_drop_forgets_a_departed_key() -> None:
    tr = StallTracker()
    tr.observe("a", 1)
    tr.observe("a", 1)
    tr.drop("a")
    assert tr.observe("a", 1) == 1  # re-seen from scratch after drop
    tr.drop("missing")  # dropping an unknown key is a no-op
