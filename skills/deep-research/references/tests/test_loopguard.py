"""Loop-guard tests (Lens 12 find 5): token-Jaccard >= 0.8 -> partial:loop."""

import pytest

from research_harness.loopguard import (
    DEFAULT_MAX_REPEATS,
    LOOP_THRESHOLD,
    LoopGuard,
    token_jaccard,
    tokenize,
)


def test_tokenize_lowercases_and_splits_on_punctuation():
    assert tokenize("Rust vs. Go: backend services (2026)!") == frozenset(
        {"rust", "vs", "go", "backend", "services", "2026"}
    )
    assert tokenize("") == frozenset()


def test_token_jaccard_is_symmetric_and_bounded():
    a = "rust vs go backend services"
    b = "rust versus go for backend services"
    assert token_jaccard(a, b) == pytest.approx(token_jaccard(b, a))
    assert 0.0 <= token_jaccard(a, b) <= 1.0
    assert token_jaccard(a, a) == 1.0
    assert token_jaccard("", "") == 0.0
    assert token_jaccard("apples", "oranges") == 0.0


def test_defaults_match_the_lens_thresholds():
    assert LOOP_THRESHOLD == 0.8
    assert DEFAULT_MAX_REPEATS == 2


def test_first_sighting_is_not_a_repeat():
    guard = LoopGuard()
    verdict = guard.observe("rust vs go backend services 2026")
    assert not verdict.repeated
    assert verdict.similarity == 0.0
    assert verdict.nearest is None
    assert verdict.repeats == 0
    assert not verdict.tripped
    assert guard.status is None


def test_exact_repeat_is_caught_via_query_hash_even_with_case_and_spacing():
    guard = LoopGuard()
    guard.observe("Rust vs Go backend services")
    verdict = guard.observe("  rust   VS go backend services ")
    assert verdict.repeated
    assert verdict.similarity == 1.0
    assert verdict.repeats == 1


def test_near_duplicate_at_or_above_threshold_is_a_repeat():
    guard = LoopGuard()
    guard.observe("solid state battery energy density 2026 review")
    # 6 shared of 7 union tokens -> 0.857 >= 0.8
    verdict = guard.observe("solid state battery energy density review")
    assert verdict.repeated
    assert verdict.similarity >= 0.8
    assert verdict.nearest == "solid state battery energy density 2026 review"


def test_reformulation_below_threshold_is_progress():
    guard = LoopGuard()
    guard.observe("solid state battery energy density 2026 review")
    verdict = guard.observe("QuantumScape anode-free cell cycle life data")
    assert not verdict.repeated
    assert verdict.repeats == 0


def test_trips_to_partial_loop_after_n_repeats():
    guard = LoopGuard(max_repeats=2)
    guard.observe("who is the ceo of acme corp")
    first = guard.observe("who is the ceo of acme corp")
    assert first.repeated and not first.tripped
    second = guard.observe("who is the current ceo of acme corp")
    assert second.repeated
    assert second.repeats == 2
    assert second.tripped
    assert second.status == "partial:loop"
    assert guard.tripped
    assert guard.status == "partial:loop"


def test_capability_and_provider_scope_the_exact_hash_but_not_the_jaccard():
    guard = LoopGuard()
    guard.observe(
        "acme corp revenue 2025", capability="web", provider="exa.web_search_exa"
    )
    # Same words on another provider: not the same query_hash, but token-identical
    # text IS a near-duplicate (the loop guard is about the agent repeating itself).
    verdict = guard.observe(
        "acme corp revenue 2025", capability="web", provider="tavily.tavily_search"
    )
    assert verdict.repeated
    assert verdict.similarity == 1.0


def test_window_limits_how_far_back_near_duplicates_are_compared():
    guard = LoopGuard(window=1)
    guard.observe("alpha beta gamma delta epsilon")
    guard.observe("completely different words here now")
    # The first query fell out of the window, so only exact hashes still match.
    verdict = guard.observe("alpha beta gamma delta epsilon zeta")
    assert not verdict.repeated


def test_zero_new_urls_for_two_rounds_marks_the_subquestion_open():
    guard = LoopGuard(no_progress_rounds=2)
    first = guard.observe_results("q1", ["https://a.example/1", "https://b.example/2"])
    assert first.new_urls == 2 and first.stalled_rounds == 0 and not first.mark_open
    second = guard.observe_results("q1", ["https://a.example/1"])
    assert second.new_urls == 0 and second.stalled_rounds == 1 and not second.mark_open
    third = guard.observe_results("q1", ["https://B.example/2/"])  # same URL, noisy
    assert third.new_urls == 0
    assert third.stalled_rounds == 2
    assert third.mark_open
    # A different sub-question keeps its own progress counter.
    other = guard.observe_results("q2", [])
    assert other.stalled_rounds == 1 and not other.mark_open


def test_new_url_resets_the_stall_counter():
    guard = LoopGuard(no_progress_rounds=2)
    guard.observe_results("q1", ["https://a.example/1"])
    guard.observe_results("q1", [])
    fresh = guard.observe_results("q1", ["https://c.example/3"])
    assert fresh.new_urls == 1
    assert fresh.stalled_rounds == 0


def test_invalid_configuration_is_rejected():
    with pytest.raises(ValueError):
        LoopGuard(threshold=1.5)
    with pytest.raises(ValueError):
        LoopGuard(max_repeats=0)
