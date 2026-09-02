#!/usr/bin/env python3
"""Origin tracing: independence is not distinct-URL counting.

Two resolved sources corroborate a claim only when (1) origin_id differs,
(2) organisation differs, (3) neither citation closure contains the other
origin, and (4) closures share no upstream origin.
"""
from __future__ import annotations

from itertools import combinations
from typing import Any
from urllib.parse import urlparse

INDEPENDENT = "INDEPENDENTLY-CORROBORATED"
SINGLE = "SINGLE-SOURCED"


def canon(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def origin_id(src: dict[str, Any]) -> str:
    explicit = canon(str(src.get("origin_id") or ""))
    if explicit:
        return explicit
    org = canon(str(src.get("organisation") or ""))
    if org:
        return org
    url = str(src.get("url") or "")
    host = (urlparse(url).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host:
        return host
    raise ValueError(f"source {src.get('id')!r} has no origin_id")


def cites_of(src: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for item in src.get("cites") or []:
        c = canon(str(item))
        if c:
            out.append(c)
    return out


def citation_closure(
    src: dict[str, Any], by_origin: dict[str, dict[str, Any]] | None = None
) -> set[str]:
    by_origin = by_origin or {}
    own = origin_id(src)
    seen: set[str] = {own}
    stack = list(cites_of(src))
    while stack:
        nid = stack.pop()
        if nid in seen:
            continue
        seen.add(nid)
        other = by_origin.get(nid)
        if other is not None:
            stack.extend(cites_of(other))
    return seen


def index_by_origin(sources: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    idx: dict[str, dict[str, Any]] = {}
    for src in sources:
        idx[origin_id(src)] = src
    return idx


def pair_independence(
    a: dict[str, Any],
    b: dict[str, Any],
    by_origin: dict[str, dict[str, Any]] | None = None,
) -> tuple[bool, str]:
    oa, ob = origin_id(a), origin_id(b)
    if oa == ob:
        return False, "same-origin"
    org_a = canon(str(a.get("organisation") or ""))
    org_b = canon(str(b.get("organisation") or ""))
    if org_a and org_b and org_a == org_b:
        return False, "same-organisation"
    by_origin = by_origin or {}
    ca = citation_closure(a, by_origin)
    cb = citation_closure(b, by_origin)
    if oa in (cb - {ob}):
        return False, "second-cites-first"
    if ob in (ca - {oa}):
        return False, "first-cites-second"
    up_a = ca - {oa}
    up_b = cb - {ob}
    shared = sorted(up_a & up_b)
    if shared:
        return False, "shared-upstream:" + ",".join(shared)
    return True, "independent"


def independent_origin_count(sources: list[dict[str, Any]]) -> int:
    """Size of a maximum pairwise-independent origin set (greedy)."""
    if not sources:
        return 0
    by_origin = index_by_origin(sources)
    reps: list[dict[str, Any]] = []
    seen: set[str] = set()
    for src in sources:
        oid = origin_id(src)
        if oid in seen:
            continue
        seen.add(oid)
        reps.append(src)
    kept: list[dict[str, Any]] = []
    for cand in reps:
        if all(pair_independence(cand, k, by_origin)[0] for k in kept):
            kept.append(cand)
    return len(kept)


def naive_url_count(sources: list[dict[str, Any]]) -> int:
    urls = {
        str(s.get("url") or "").strip()
        for s in sources
        if str(s.get("url") or "").strip()
    }
    return len(urls)
