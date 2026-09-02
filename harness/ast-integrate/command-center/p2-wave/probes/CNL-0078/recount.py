#!/usr/bin/env python3
"""Independent recount: group by mechanism field only (no Jaccard, no metrics.py)."""
from __future__ import annotations

from collections import defaultdict
from typing import Any


def recount(ledger: list[dict[str, Any]], required: dict[str, list[str]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for idea in ledger:
        groups[str(idea.get("mechanism") or idea.get("id"))].append(idea)
    subq: set[str] = set()
    cats: set[str] = set()
    evid: set[str] = set()
    for rows in groups.values():
        for row in rows:
            cats.add(str(row.get("category")))
            evid.add(str(row.get("evidence_class")))
            sq = row.get("subquestions") or []
            if isinstance(sq, list):
                subq.update(str(x) for x in sq)
            elif sq:
                subq.add(str(sq))

    def ratio(got: set[str], need: list[str]) -> float:
        return len(got & set(need)) / len(need) if need else 1.0

    parts = {
        "subquestions": round(ratio(subq, required["subquestions"]), 6),
        "categories": round(ratio(cats, required["categories"]), 6),
        "evidence_classes": round(ratio(evid, required["evidence_classes"]), 6),
    }
    return {
        "method": "groupby-mechanism-field-only",
        "unique_ideas": len(groups),
        "n_raw": len(ledger),
        "completeness_score": round(min(parts.values()), 6),
        "completeness_parts": parts,
        "mechanisms": sorted(groups),
    }
