"""CNF-0132 subset regression control: a third independent upstream raises rank.

From the receipt's published control detail: subset_rank=2 full_rank=3
cache_rank=1 naive_cache=2. Rebuilt 2026-10-26 (wave-3 shard 7).
"""
from __future__ import annotations

from typing import Any

import graph


def subset_regression(frame: dict[str, Any]) -> dict[str, int]:
    """Drop planted-third-c: THIRD drops 3 -> 2; cache stays 1; naive says 2."""
    subset = {
        "records": [r for r in frame["records"] if r["record_id"] != "planted-third-c"],
        "probe_upstreams": {
            k: v
            for k, v in frame["probe_upstreams"].items()
            if not k.startswith("probe-third-c")
        },
    }
    sub = graph.build(subset)
    full = graph.build(frame)
    cache = full["per_claim"]["C-CACHE-COLLAPSE"]
    third_full = full["per_claim"]["C-THIRD-INDEPENDENT"]
    third_sub = sub["per_claim"]["C-THIRD-INDEPENDENT"]
    return {
        "subset_rank": third_sub["rank"],
        "full_rank": third_full["rank"],
        "cache_rank": cache["rank"],
        "naive_cache": cache["apparent_n"],
    }
