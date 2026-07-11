"""Tests for core/eta.py — ETA model library (p50/p90 + provenance)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.eta import (  # noqa: E402
    ewma_throughput_eta,
    linear_frac_eta,
    per_phase_weighted_eta,
    prior_eta,
    steady_state_window_eta,
)
from core.models import Provenance  # noqa: E402


class TestLinearFrac:
    def test_unknown_fraction(self):
        eta = linear_frac_eta(None, 100.0)
        assert eta.provenance == Provenance.NONE
        assert eta.p50 is None

    def test_zero_elapsed(self):
        assert linear_frac_eta(0.5, 0.0).provenance == Provenance.NONE

    def test_zero_fraction(self):
        assert linear_frac_eta(0.0, 100.0).provenance == Provenance.NONE

    def test_normal(self):
        eta = linear_frac_eta(0.25, 100.0)
        # 100s got 25% -> 300s remaining at p50
        assert eta.p50 == 300.0
        assert eta.p90 is not None and eta.p90 > eta.p50
        assert eta.provenance == Provenance.MEASURED

    def test_overshoot_widens_not_clamps(self):
        eta = linear_frac_eta(1.5, 100.0)
        assert eta.p50 == 0.0
        assert eta.p90 is not None and eta.p90 > 0  # overrun surfaced as band
        assert eta.provenance == Provenance.MEASURED

    def test_complete_exact(self):
        eta = linear_frac_eta(1.0, 100.0)
        assert eta.p50 == 0.0
        assert eta.p90 == 0.0


class TestEwmaThroughput:
    def test_unknown_total(self):
        assert ewma_throughput_eta(5.0, None, 2.0).provenance == Provenance.NONE

    def test_unknown_throughput(self):
        assert ewma_throughput_eta(5.0, 10.0, None).provenance == Provenance.NONE

    def test_nonpositive_throughput(self):
        assert ewma_throughput_eta(5.0, 10.0, 0.0).provenance == Provenance.NONE

    def test_normal(self):
        eta = ewma_throughput_eta(4.0, 10.0, 2.0)
        assert eta.p50 == 3.0  # 6 units / 2 per sec
        assert eta.p90 is not None and eta.p90 > eta.p50

    def test_overshoot(self):
        eta = ewma_throughput_eta(12.0, 10.0, 2.0)
        assert eta.p50 == 0.0
        assert eta.p90 == 1.0  # 2 units over / 2 per sec


class TestPerPhaseWeighted:
    _phases = [("prep", 10.0), ("run", 20.0), ("post", 5.0)]

    def test_unknown_throughput(self):
        assert (
            per_phase_weighted_eta("run", 0.0, self._phases, None).provenance
            == Provenance.NONE
        )

    def test_unknown_phase(self):
        assert (
            per_phase_weighted_eta("ghost", 0.0, self._phases, 1.0).provenance
            == Provenance.NONE
        )

    def test_normal_sums_current_plus_later(self):
        # in 'run', 5 done of 20 -> 15 left + 5 post = 20 units / 2 = 10s
        eta = per_phase_weighted_eta("run", 5.0, self._phases, 2.0)
        assert eta.p50 == 10.0
        assert eta.provenance == Provenance.MEASURED

    def test_last_phase_no_later(self):
        eta = per_phase_weighted_eta("post", 1.0, self._phases, 2.0)
        assert eta.p50 == 2.0  # 4 units left / 2

    def test_in_phase_overshoot(self):
        eta = per_phase_weighted_eta("post", 10.0, self._phases, 1.0)
        assert eta.p50 == 0.0
        assert eta.p90 == 5.0  # 5 over / 1


class TestSteadyStateWindow:
    def test_unknown_remaining(self):
        assert steady_state_window_eta([1.0], None).provenance == Provenance.NONE

    def test_empty_window(self):
        assert steady_state_window_eta([], 10.0).provenance == Provenance.NONE

    def test_nonpositive_rate(self):
        assert steady_state_window_eta([0.0, 0.0], 10.0).provenance == Provenance.NONE

    def test_normal_spread_widens(self):
        eta = steady_state_window_eta([2.0, 2.0, 4.0], 10.0)
        # median rate 2.0 -> p50 = 5.0; spread = 4/2 = 2 widens p90
        assert eta.p50 == 5.0
        assert eta.p90 is not None and eta.p90 == 5.0 * 1.5 * 2.0

    def test_overshoot(self):
        eta = steady_state_window_eta([2.0], -4.0)
        assert eta.p50 == 0.0
        assert eta.p90 == 2.0


class TestPriorEta:
    def test_no_prior(self):
        assert prior_eta(None, 10.0).provenance == Provenance.NONE

    def test_nonpositive_prior(self):
        assert prior_eta(0.0, 10.0).provenance == Provenance.NONE

    def test_within_prior(self):
        eta = prior_eta(100.0, 40.0)
        assert eta.p50 == 60.0
        assert eta.provenance == Provenance.PRIOR

    def test_overdue_does_not_slide_clock(self):
        eta = prior_eta(100.0, 130.0)
        assert eta.p50 == 0.0
        assert eta.p90 == 30.0  # 30s overdue surfaced as band
        assert eta.provenance == Provenance.PRIOR
