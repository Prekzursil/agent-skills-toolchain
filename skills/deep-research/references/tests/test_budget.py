"""Budget tracker + regime tests (Lens 12 find 3; injected clock, no sleeps)."""

import pytest

from research_harness.budget import (
    CONVERGE,
    EFFORT_CALLS,
    EXPLORE,
    FINALIZE,
    Budget,
    estimate_tokens,
)


class FakeClock:
    def __init__(self, start=1000.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def _budget(**kwargs):
    clock = FakeClock()
    kwargs.setdefault("max_calls", 20)
    return Budget(clock=clock, **kwargs), clock


def test_fresh_budget_is_in_explore_and_allows_everything():
    budget, _ = _budget()
    assert budget.used_calls == 0
    assert budget.fraction_used == 0.0
    assert budget.regime == EXPLORE
    assert budget.allows_new_search
    assert budget.allows_metered
    assert budget.terminal_status is None


def test_regime_thresholds_explore_converge_finalize():
    budget, _ = _budget(max_calls=20)
    budget.spend(calls=11)  # 55%
    assert budget.regime == EXPLORE
    budget.spend(calls=1)  # 60% -> converge
    assert budget.regime == CONVERGE
    budget.spend(calls=5)  # 85% -> still converge (finalize is strictly > 85%)
    assert budget.regime == CONVERGE
    budget.spend(calls=1)  # 90% -> finalize
    assert budget.regime == FINALIZE


def test_converge_stops_metered_spend_but_still_searches():
    budget, _ = _budget(max_calls=10)
    budget.spend(calls=7)
    assert budget.regime == CONVERGE
    assert budget.allows_new_search
    assert not budget.allows_metered


def test_finalize_is_beast_mode_no_new_searches_partial_budget():
    budget, _ = _budget(max_calls=10)
    budget.spend(calls=9)
    assert budget.regime == FINALIZE
    assert not budget.allows_new_search
    assert not budget.allows_metered
    assert budget.terminal_status == "partial:budget"
    assert budget.binding_axis == "calls"


def test_wall_clock_axis_drives_partial_timeout():
    budget, clock = _budget(max_calls=100, max_seconds=600)
    clock.advance(540)  # 90% of the wall clock, 0% of calls
    assert budget.binding_axis == "seconds"
    assert budget.regime == FINALIZE
    assert budget.terminal_status == "partial:timeout"
    assert budget.seconds_left == pytest.approx(60)


def test_token_axis_counts_toward_the_binding_fraction():
    budget, _ = _budget(max_calls=100, max_tokens=1000)
    budget.spend(calls=1, tokens=900)
    assert budget.binding_axis == "tokens"
    assert budget.regime == FINALIZE
    assert budget.terminal_status == "partial:budget"


def test_exhausted_and_overspend_are_reported_not_raised():
    budget, _ = _budget(max_calls=3)
    budget.spend(calls=3)
    assert budget.exhausted
    budget.spend(calls=1)  # the loop may already be mid-call; record honestly
    assert budget.used_calls == 4
    assert budget.fraction_used == pytest.approx(4 / 3)
    assert budget.calls_left == 0


def test_spend_rejects_negative_amounts_and_zero_max_calls():
    budget, _ = _budget()
    with pytest.raises(ValueError):
        budget.spend(calls=-1)
    with pytest.raises(ValueError):
        Budget(max_calls=0)


def test_status_line_is_the_one_line_loop_prefix():
    budget, clock = _budget(max_calls=20, max_seconds=600)
    budget.spend(calls=11)
    clock.advance(240)
    line = budget.status_line()
    assert line.startswith("Budget: 11/20 calls")
    assert "6 min left" in line
    assert "regime=explore" in line


def test_status_line_without_wall_clock_or_tokens_is_still_stable():
    budget, _ = _budget(max_calls=5)
    budget.spend(calls=2, tokens=800)
    assert budget.status_line() == "Budget: 2/5 calls, ~800 tokens, regime=explore"


def test_can_afford_checks_an_allotment_against_calls_left():
    budget, _ = _budget(max_calls=10)
    budget.spend(calls=6)
    assert budget.can_afford(EFFORT_CALLS["fact"])
    assert not budget.can_afford(EFFORT_CALLS["compare"])


def test_effort_classes_are_the_anthropic_style_allotments():
    assert EFFORT_CALLS == {"fact": 3, "compare": 8, "deep": 15}


def test_estimate_tokens_is_a_deterministic_chars_over_four_heuristic():
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("a" * 4000) == 1000
    assert estimate_tokens("abc") == 1  # never rounds a non-empty text to zero
