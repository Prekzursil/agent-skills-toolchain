"""Canonical monitor state rebuild (IMP-0225)."""
from __future__ import annotations

from typing import Any


CANONICAL_FIELDS = (
    "run_id",
    "completed_ids",
    "in_flight_ids",
    "open_ids",
    "dispatch_count",
    "harvest_count",
    "units",
)


def diff_canonical(a: dict[str, Any], b: dict[str, Any]) -> list[str]:
    diffs = []
    for key in CANONICAL_FIELDS:
        if a.get(key) != b.get(key):
            diffs.append(key)
    return diffs
