#!/usr/bin/env python3
"""Class-expansion trigger for a pre-registered error-rate threshold.

strict_gt: fire when rate > threshold; equal-to-threshold is silent.
Expansion enqueues the entire stratum population, not the sample.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import adjudicate as A  # noqa: E402


def should_expand(rate: float | None, threshold: float, defined: bool) -> bool:
    if not defined or rate is None:
        return False
    return rate > threshold


def decide(
    sample_rows: list[dict],
    population_ids: list[str],
    threshold: float,
    stratum_id: str,
    already_expanded: set[str] | None = None,
) -> dict:
    already = set(already_expanded or [])
    counts = A.error_counts(sample_rows)
    fired = should_expand(counts["rate"], threshold, counts["defined"])
    pop = sorted(set(population_ids))
    if not fired:
        return {
            "already_skipped": [],
            "class_size": len(pop),
            "defined": counts["defined"],
            "enqueued": [],
            "fired": False,
            "k": counts["k"],
            "n": counts["n"],
            "rate": counts["rate"],
            "stratum_id": stratum_id,
            "threshold": threshold,
        }
    enqueued = [cid for cid in pop if cid not in already]
    skipped = [cid for cid in pop if cid in already]
    return {
        "already_skipped": skipped,
        "class_size": len(pop),
        "defined": counts["defined"],
        "enqueued": enqueued,
        "fired": True,
        "k": counts["k"],
        "n": counts["n"],
        "rate": counts["rate"],
        "stratum_id": stratum_id,
        "threshold": threshold,
    }
