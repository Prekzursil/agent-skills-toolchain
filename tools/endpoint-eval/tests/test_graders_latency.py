"""Golden tests for graders.latency (AA definitions; nearest-rank p50/p95; n < 20 insufficient)."""

from __future__ import annotations

import pytest
from graders.latency import (
    MIN_TRUSTED_N,
    Sample,
    percentile,
    summarize,
    tokens_per_second,
)


def test_percentile_nearest_rank_hand_values() -> None:
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert percentile(values, 50) == 30.0
    assert percentile(values, 95) == 50.0
    assert percentile([7.0], 95) == 7.0
    assert percentile([3.0, 1.0, 2.0], 50) == 2.0
    assert percentile([1.0, 2.0, 3.0, 4.0], 25) == 1.0
    assert percentile([], 50) == 0.0


def test_percentile_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        percentile([1.0], 0)
    with pytest.raises(ValueError):
        percentile([1.0], 101)


def test_tokens_per_second_last_80_percent_of_chunks() -> None:
    # 10 chunks at 100 ms spacing; the last 80 % window is chunks 3..10 (8 chunks, 700 ms span).
    sample = Sample(
        ttft_ms=100.0,
        e2e_ms=1000.0,
        completion_tokens=10,
        chunk_ms=tuple(range(100, 1100, 100)),
    )
    assert tokens_per_second(sample) == pytest.approx(7 / 0.7)


def test_tokens_per_second_falls_back_to_e2e_minus_ttft() -> None:
    sample = Sample(ttft_ms=200.0, e2e_ms=1200.0, completion_tokens=50)
    assert tokens_per_second(sample) == pytest.approx(50.0)


def test_tokens_per_second_zero_when_no_time_elapsed() -> None:
    assert (
        tokens_per_second(Sample(ttft_ms=100.0, e2e_ms=100.0, completion_tokens=5))
        == 0.0
    )
    flat = Sample(ttft_ms=1.0, e2e_ms=1.0, completion_tokens=2, chunk_ms=(1.0, 1.0))
    assert tokens_per_second(flat) == 0.0
    single_chunk = Sample(ttft_ms=1.0, e2e_ms=3.0, completion_tokens=1, chunk_ms=(1.0,))
    assert tokens_per_second(single_chunk) == pytest.approx(500.0)


def test_summarize_insufficient_under_twenty_but_still_numeric() -> None:
    samples = [
        Sample(ttft_ms=100.0 + i, e2e_ms=1000.0 + i, completion_tokens=10)
        for i in range(19)
    ]
    summary = summarize(samples)
    assert summary["status"] == "insufficient"
    assert summary["n"] == 19
    assert summary["ttft_ms_p50"] == 109.0
    assert summary["ttft_ms_p95"] == 118.0
    assert summary["e2e_ms_p50"] == 1009.0
    assert summary["e2e_ms_p95"] == 1018.0
    assert summary["tok_per_s_last80"] > 0


def test_summarize_ok_at_twenty() -> None:
    samples = [
        Sample(ttft_ms=50.0, e2e_ms=500.0, completion_tokens=45)
        for _ in range(MIN_TRUSTED_N)
    ]
    summary = summarize(samples)
    assert summary["status"] == "ok"
    assert summary["n"] == 20
    assert summary["tok_per_s_last80"] == pytest.approx(100.0)
    assert set(summary) == {
        "ttft_ms_p50",
        "ttft_ms_p95",
        "e2e_ms_p50",
        "e2e_ms_p95",
        "tok_per_s_last80",
        "n",
        "status",
    }


def test_summarize_empty() -> None:
    summary = summarize([])
    assert summary["n"] == 0
    assert summary["status"] == "insufficient"
    assert summary["ttft_ms_p95"] == 0.0
    assert summary["tok_per_s_last80"] == 0.0
