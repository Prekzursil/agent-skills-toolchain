"""R9: the unattended cron must not start without a hard ceiling.

CSIE-DESIGN.md:201 — "Nightly stays OFF until the ceiling exists." The harness deliberately
defaults to NO wall-clock cap (a hard cap once produced a false TIMEOUT on a wave whose
artifacts were complete), which is right for an interactive run and unsafe for a cron. So the
ceiling lives in the engine and is checked BEFORE fan-out.

Every gate here fails CLOSED: an unknown quota, an unreadable count, or a missing watchdog
refuses the wave rather than assuming it is fine.
"""

from __future__ import annotations

import pytest

from engine import ceiling


def _c(**kw):
    base = dict(
        max_units=48, max_concurrent=48, wall_clock_s=4 * 3600, per_unit_watchdog_s=1800
    )
    base.update(kw)
    return ceiling.WaveCeiling(**base)


def test_allows_a_wave_inside_every_limit():
    ok, reason = ceiling.check_wave(n_units=10, ceiling=_c(), quota_ok=True)
    assert ok is True and reason == "ok"


def test_rejects_more_units_than_max():
    ok, reason = ceiling.check_wave(n_units=49, ceiling=_c(max_units=48), quota_ok=True)
    assert ok is False and "max_units" in reason


def test_rejects_concurrency_above_max():
    ok, reason = ceiling.check_wave(
        n_units=10, ceiling=_c(max_concurrent=64), quota_ok=True
    )
    assert ok is False and "max_concurrent" in reason


def test_unknown_quota_fails_closed():
    """No budget API exists (AgentBridge get_budget was retired), so quota is caller-supplied.
    Unknown must refuse — an unattended cron cannot ask."""
    ok, reason = ceiling.check_wave(n_units=1, ceiling=_c(), quota_ok=None)
    assert ok is False and "quota" in reason


def test_exhausted_quota_refuses():
    ok, reason = ceiling.check_wave(n_units=1, ceiling=_c(), quota_ok=False)
    assert ok is False and "quota" in reason


@pytest.mark.parametrize("field", ["wall_clock_s", "per_unit_watchdog_s"])
def test_missing_or_unbounded_timeout_is_rejected(field):
    """A cron with no wall-clock ceiling or no per-unit watchdog is exactly the R9 hazard."""
    ok, reason = ceiling.check_wave(n_units=1, ceiling=_c(**{field: 0}), quota_ok=True)
    assert ok is False and field in reason


def test_zero_units_is_refused_not_silently_passed():
    ok, reason = ceiling.check_wave(n_units=0, ceiling=_c(), quota_ok=True)
    assert ok is False and "n_units" in reason


def test_watchdog_cannot_exceed_the_wave_ceiling():
    """A per-unit watchdog longer than the whole wave can never fire — it is not a control."""
    ok, reason = ceiling.check_wave(
        n_units=1, ceiling=_c(wall_clock_s=600, per_unit_watchdog_s=1800), quota_ok=True
    )
    assert ok is False and "watchdog" in reason


def test_default_ceiling_is_self_consistent():
    """The shipped default must pass its own gate, or the cron can never start."""
    ok, reason = ceiling.check_wave(n_units=1, ceiling=ceiling.DEFAULT, quota_ok=True)
    assert ok is True, reason
    assert ceiling.DEFAULT.per_unit_watchdog_s <= ceiling.DEFAULT.wall_clock_s
