"""TST-0265 probe lane adapter over the library counter."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.quota.unique_ideas import (  # noqa: E402
    STOPPING_JACCARD_THRESHOLD,
    _mechanism_key,
    _raw_jaccard,
    stopping_unique_count,
)

TARGET_UNIQUE = 100
TOLERANCE = 0.05


def pair_signal(left: str, right: str) -> dict:
    """Which signal fires for one pair (S1 raw Jaccard, S2 folded key)."""
    s1 = _raw_jaccard(left, right) >= STOPPING_JACCARD_THRESHOLD
    s2 = _mechanism_key(left) == _mechanism_key(right)
    return {"s1_fires": s1, "s2_fires": s2, "fired": s1 or s2}


def run_count(texts: list[str]) -> dict:
    info = stopping_unique_count(texts)
    info["target_ge_100_met"] = info["post_dedup_count"] >= TARGET_UNIQUE
    info["distinct_collapse_ok"] = info["collapse_ratio"] < TOLERANCE
    return info
