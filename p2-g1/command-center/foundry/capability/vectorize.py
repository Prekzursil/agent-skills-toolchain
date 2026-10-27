"""Coverage vectors for foundry capability candidates (IMP-0177)."""
from __future__ import annotations

from typing import Any

from .taxonomy import capability_ids, load_taxonomy


def _default_candidates() -> list[dict[str, Any]]:
    return [
        {
            "id": "cand.imported.empty-covers",
            "stages": [{"id": "s0", "kind": "noop", "covers": []}],
        },
        {
            "id": "cand.imported.single-bit",
            "stages": [{"id": "s1", "kind": "watch", "covers": ["watchlist"]}],
        },
        {
            "id": "cand.imported.multi",
            "stages": [
                {"id": "s1", "kind": "hunt", "covers": ["gem-hunt"]},
                {"id": "s2", "kind": "cite", "covers": ["citation"]},
            ],
        },
    ]


def load_candidates() -> list[dict[str, Any]]:
    return list(_default_candidates())


def vectorize(candidate: dict[str, Any], tax: dict[str, Any] | None = None) -> dict[str, Any]:
    tax = tax or load_taxonomy()
    axis = capability_ids(tax)
    covers: set[str] = set()
    for stage in candidate.get("stages") or []:
        for cap in stage.get("covers") or []:
            covers.add(str(cap))
    bits = [1 if cap in covers else 0 for cap in axis]
    return {
        "candidate_id": candidate.get("id"),
        "bits": bits,
        "covers": sorted(covers),
    }


def vectorize_all(candidates: list[dict[str, Any]], tax: dict[str, Any] | None = None) -> dict[str, Any]:
    tax = tax or load_taxonomy()
    vectors = [vectorize(c, tax) for c in candidates]
    null_ids = [v["candidate_id"] for v in vectors if v.get("bits") is None]
    return {
        "candidate_count": len(candidates),
        "vector_count": len(vectors),
        "null_count": len(null_ids),
        "null_ids": null_ids,
        "coverage_complete": len(null_ids) == 0 and len(vectors) == len(candidates),
        "vectors": vectors,
    }
