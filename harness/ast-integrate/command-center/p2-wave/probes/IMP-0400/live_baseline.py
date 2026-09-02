#!/usr/bin/env python3
"""CURRENT live selection arm for IMP-0400.

This module is the pre-router live selector. It MUST NOT import router.py.
Live behavior (the estate default before a dedicated router is armed):
  1. substring-match any trigger phrase in the query (case-insensitive);
  2. if nothing matches, return the top-k capabilities by popularity.

That popularity pad is the live flooding behavior the new router is measured
against. Reconstructing these selections from router scores after the fact is
the failure class baseline-reconstructed-after-the-fact.
"""
from __future__ import annotations

from typing import Any


def live_select(query: str, capabilities: list[dict[str, Any]], k: int) -> list[str]:
    q = query.lower()
    hits: list[str] = []
    seen: set[str] = set()
    for cap in capabilities:
        cid = str(cap["id"])
        for trig in cap.get("triggers") or []:
            if trig and trig.lower() in q and cid not in seen:
                hits.append(cid)
                seen.add(cid)
                break
        if len(hits) >= k:
            return hits[:k]
    if hits:
        return hits[:k]
    ranked = sorted(
        capabilities,
        key=lambda c: (-int(c.get("popularity") or 0), str(c["id"])),
    )
    return [str(c["id"]) for c in ranked[:k]]
