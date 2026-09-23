"""Sufficiency gate tests (Lens 12 find 6): >= 2 sources graded >= B, corroboration >= 1."""

import pytest

from research_harness.grading import Source, grade_source
from research_harness.sufficiency import (
    INSUFFICIENT,
    MAX_FOLLOW_UPS,
    PARTIAL,
    SUFFICIENT,
    follow_up_query,
    gate,
    judge_sufficiency,
)

REF = 2026


def _grade(url, provider, year, corrob):
    return grade_source(
        Source("t", url, provider, year), corroboration_count=corrob, reference_year=REF
    )


A_CORROB = _grade("https://doi.org/10.1/a", "scholarly-access", 2026, 2)
B_CORROB = _grade("https://en.wikipedia.org/x", "exa", 2025, 2)
B_SINGLE = _grade("https://github.com/x/y", "exa", 2026, 1)
C_SINGLE = _grade("https://forum.example/x", "unknown", 2020, 1)
C_CORROB = _grade("https://blog.example/x", "unknown", 2026, 3)


def test_two_strong_sources_with_one_corroborated_is_sufficient():
    verdict = judge_sufficiency([A_CORROB, B_SINGLE])
    assert verdict.verdict == SUFFICIENT
    assert verdict.sufficient
    assert verdict.strong_sources == 2
    assert verdict.corroborated == 1


def test_two_strong_but_uncorroborated_sources_is_only_partial():
    verdict = judge_sufficiency([B_SINGLE, B_SINGLE])
    assert verdict.verdict == PARTIAL
    assert not verdict.sufficient


def test_one_strong_source_is_partial_even_if_corroborated():
    assert judge_sufficiency([A_CORROB]).verdict == PARTIAL
    assert judge_sufficiency([A_CORROB, C_SINGLE, C_CORROB]).verdict == PARTIAL


def test_only_tier_c_or_nothing_is_insufficient():
    assert judge_sufficiency([C_SINGLE, C_CORROB]).verdict == INSUFFICIENT
    assert judge_sufficiency([]).verdict == INSUFFICIENT
    assert judge_sufficiency([]).strong_sources == 0


def test_gate_writes_when_sufficient():
    decision = gate("Who leads Acme Corp in 2026?", [A_CORROB, B_CORROB])
    assert decision.action == "write"
    assert decision.query is None
    assert decision.verdict.sufficient


def test_gate_allows_exactly_one_bounded_follow_up_then_marks_open():
    first = gate("Who leads Acme Corp in 2026?", [C_SINGLE], attempts=0)
    assert first.action == "follow_up"
    assert first.query is not None and first.query != "Who leads Acme Corp in 2026?"
    second = gate("Who leads Acme Corp in 2026?", [C_SINGLE], attempts=1)
    assert second.action == "mark_open"
    assert second.query is None
    assert second.status == "partial:sources"
    assert first.status is None
    assert MAX_FOLLOW_UPS == 1


def test_follow_up_query_is_a_deterministic_reformulation_with_entities_and_dates():
    query = follow_up_query("Who leads Acme Corp in 2026?", attempts=0)
    assert query == 'leads "Acme Corp" in 2026 primary source'
    assert follow_up_query("Who leads Acme Corp in 2026?", attempts=0) == query
    assert follow_up_query("Who leads Acme Corp in 2026?", attempts=1) is None


def test_follow_up_query_avoids_a_query_already_tried():
    original = "How many employees does Acme Corp have?"
    first = follow_up_query(original, attempts=0)
    assert first == 'employees does "Acme Corp" have primary source'
    alternative = follow_up_query(original, attempts=0, seen=[first])
    assert alternative != first
    assert alternative == 'employees does "Acme Corp" have official report'


def test_follow_up_query_without_entities_still_reformulates():
    assert follow_up_query("what is the market size?", attempts=0) == (
        "the market size primary source"
    )


def test_gate_rejects_negative_attempts():
    with pytest.raises(ValueError):
        gate("q", [], attempts=-1)
