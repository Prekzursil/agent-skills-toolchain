#!/usr/bin/env python3
"""Independence collapse for practitioner-reported failures.

RES-0115 / 05-ECO section 6:
  * sources that share one upstream primitive are ONE signal
  * reporters that quote one another are ONE reporter
  * a thread-container URL is not a reporter
  * a search-index ancestor (thread or parent comment that does not itself
    state the failure) is not an extra reporter of the descendant claim
"""
from __future__ import annotations

from typing import Any


THREAD_ROLES = frozenset({"thread-container", "search-index-ancestor"})
QUOTE_ROLES = frozenset({"quote-reply", "restatement"})


class UnionFind:
    def __init__(self, ids: list[str]) -> None:
        self.parent = {i: i for i in ids}

    def find(self, x: str) -> str:
        p = self.parent[x]
        if p != x:
            self.parent[x] = self.find(p)
        return self.parent[x]

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra

    def components(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for i in self.parent:
            out.setdefault(self.find(i), []).append(i)
        return out


def _ids(reporters: list[dict[str, Any]]) -> list[str]:
    ids = []
    for r in reporters:
        rid = str(r.get("id") or "")
        if not rid:
            raise ValueError("reporter missing id")
        ids.append(rid)
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate reporter id")
    return ids


def collapse_reporters(reporters: list[dict[str, Any]]) -> dict[str, Any]:
    """Return raw count, independent count, and the recorded check."""
    if not reporters:
        return {
            "raw_reporter_count": 0,
            "independent_reporter_count": 0,
            "components": [],
            "dropped": [],
            "unions": [],
            "verdict": "empty",
        }
    by_id = {str(r["id"]): r for r in reporters}
    raw = len(reporters)
    dropped: list[dict[str, str]] = []
    kept: list[str] = []
    for r in reporters:
        rid = str(r["id"])
        role = str(r.get("role") or "report")
        if role in THREAD_ROLES:
            dropped.append({"id": rid, "reason": f"role:{role}"})
            continue
        kept.append(rid)
    if not kept:
        return {
            "raw_reporter_count": raw,
            "independent_reporter_count": 0,
            "components": [],
            "dropped": dropped,
            "unions": [{"rule": "all-dropped-as-non-reporters"}],
            "verdict": "collapsed-to-zero",
        }
    uf = UnionFind(kept)
    unions: list[dict[str, str]] = []

    authors: dict[str, list[str]] = {}
    for rid in kept:
        author = str(by_id[rid].get("author_id") or "")
        if author:
            authors.setdefault(author, []).append(rid)
    for author, group in authors.items():
        for other in group[1:]:
            uf.union(group[0], other)
            unions.append(
                {
                    "rule": "same-author",
                    "a": group[0],
                    "b": other,
                    "author_id": author,
                }
            )

    for rid in kept:
        r = by_id[rid]
        for qid in r.get("quotes_ids") or []:
            qid = str(qid)
            if qid in uf.parent:
                uf.union(rid, qid)
                unions.append({"rule": "quotes", "a": rid, "b": qid})
        parent = str(r.get("parent_id") or "")
        if parent in uf.parent and str(r.get("role") or "") in QUOTE_ROLES:
            uf.union(rid, parent)
            unions.append({"rule": "quote-reply-parent", "a": rid, "b": parent})
        dup = str(r.get("duplicate_of") or "")
        if dup in uf.parent:
            uf.union(rid, dup)
            unions.append({"rule": "duplicate-of", "a": rid, "b": dup})

    primitives: dict[str, list[str]] = {}
    for rid in kept:
        prim = str(by_id[rid].get("primitive_id") or "")
        if prim:
            primitives.setdefault(prim, []).append(rid)
    for prim, group in primitives.items():
        for other in group[1:]:
            uf.union(group[0], other)
            unions.append(
                {
                    "rule": "shared-primitive",
                    "a": group[0],
                    "b": other,
                    "primitive_id": prim,
                }
            )

    comps = uf.components()
    independent = len(comps)
    if independent == 0:
        verdict = "collapsed-to-zero"
    elif raw > 1 and independent == 1:
        verdict = "collapsed-to-one"
    elif independent < raw:
        verdict = "partial-collapse"
    else:
        verdict = "independent"
    return {
        "raw_reporter_count": raw,
        "independent_reporter_count": independent,
        "components": [
            {"root": root, "members": sorted(members)}
            for root, members in sorted(comps.items())
        ],
        "dropped": dropped,
        "unions": unions,
        "verdict": verdict,
    }


def treat_as_real(
    independent_reporter_count: int,
    vendor_doc_present: bool,
    vendor_tracker_present: bool,
    threshold: int = 2,
) -> bool:
    """Forum-only class: independent reporters at threshold AND absent from vendor docs/tracker."""
    if vendor_doc_present or vendor_tracker_present:
        return False
    return independent_reporter_count >= threshold
