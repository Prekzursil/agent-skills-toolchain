"""Latency axis (lens 08 section 2.4) with Artificial Analysis definitions, measured from OUR network.

``ttft_ms`` = first streamed chunk (first reasoning token for reasoners), ``tok_per_s_last80`` =
output speed over the last 80 % of chunks (hides the reasoning warm-up), ``e2e_ms`` = end to end.
p50/p95 are nearest-rank. Fewer than 20 samples is ``insufficient``: the numbers are still
returned, the status says they are not to be trusted.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

MIN_TRUSTED_N = 20
LAST_FRACTION = 0.8


@dataclass(frozen=True)
class Sample:
    ttft_ms: float
    e2e_ms: float
    completion_tokens: int
    chunk_ms: tuple[float, ...] = ()


def percentile(values: Sequence[float], p: int) -> float:
    """Nearest-rank percentile; 0.0 for an empty sequence."""
    if not 1 <= p <= 100:
        raise ValueError(f"percentile must be in 1..100, got {p}")
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = math.ceil(p / 100 * len(ordered))
    return ordered[max(rank, 1) - 1]


def tokens_per_second(sample: Sample) -> float:
    """Output tokens/s over the last 80 % of chunks, else over the post-TTFT span."""
    if len(sample.chunk_ms) >= 2:
        window = sample.chunk_ms[
            -max(2, math.ceil(LAST_FRACTION * len(sample.chunk_ms))) :
        ]
        span_ms = window[-1] - window[0]
        return (len(window) - 1) * 1000.0 / span_ms if span_ms > 0 else 0.0
    span_ms = sample.e2e_ms - sample.ttft_ms
    return sample.completion_tokens * 1000.0 / span_ms if span_ms > 0 else 0.0


def summarize(samples: Sequence[Sample]) -> dict[str, Any]:
    ttft = [sample.ttft_ms for sample in samples]
    e2e = [sample.e2e_ms for sample in samples]
    tps = [tokens_per_second(sample) for sample in samples]
    return {
        "ttft_ms_p50": percentile(ttft, 50),
        "ttft_ms_p95": percentile(ttft, 95),
        "e2e_ms_p50": percentile(e2e, 50),
        "e2e_ms_p95": percentile(e2e, 95),
        "tok_per_s_last80": percentile(tps, 50),
        "n": len(samples),
        "status": "ok" if len(samples) >= MIN_TRUSTED_N else "insufficient",
    }
