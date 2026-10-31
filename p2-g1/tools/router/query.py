"""Capability routing query lane over the capability-index cache.

Unit IMP-0402. Serves the cached index when it matches the live tree; rebuilds
on any invalidation axis (content, mtime, truncation, schema, emptiness) and
never serves a stale or planted description.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.router.index_cache import (
    EmptyIndexError,
    assert_index_usable,
    load_or_rebuild,
)

_ROUTE_SENTINEL = "SENTINEL:IMP-0402:INDEX-INVALIDATION-SAFE"


def route_next(query: str, *, cache_path: Path, roots: list[Path]) -> dict[str, Any]:
    """Route one query through the capability index with dual invalidation."""
    outcome = load_or_rebuild(cache_path, roots)
    caps = outcome.index.get("capabilities") or []
    try:
        assert_index_usable(outcome.index)
    except EmptyIndexError:
        caps = []
    q = " ".join(str(query or "").lower().split())
    best = None
    best_desc = ""
    for cap in caps:
        desc = str(cap.get("description") or "")
        if q and q in desc.lower():
            if best is None or len(desc) < len(best_desc):
                best = cap
                best_desc = desc
    if best is None:
        return {
            "verdict": "NO-MATCH",
            "capability_id": None,
            "answer": None,
            "cache_action": outcome.action,
            "cache_reason": outcome.reason,
            "content_hash": outcome.fingerprint.content_hash,
            "sentinel": _ROUTE_SENTINEL,
        }
    return {
        "verdict": "SELECTED",
        "capability_id": best.get("capability_id"),
        "answer": best_desc,
        "cache_action": outcome.action,
        "cache_reason": outcome.reason,
        "content_hash": outcome.fingerprint.content_hash,
        "sentinel": _ROUTE_SENTINEL,
    }
