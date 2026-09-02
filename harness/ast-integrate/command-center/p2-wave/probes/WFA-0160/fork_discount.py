"""Trivial-fork / renamed-copy discount for the 160-candidate floor.

Spec :10725 forbids counting trivial forks or renamed copies toward the floor.
Two clustering methods are provided so the two named probes are not the same
rule run twice:

  fingerprint_clusters — exact (mechanisms, does-token) equality
  jaccard_clusters     — high token-Jaccard plus stripped-name equality

A renamed copy of an existing candidate must collapse. A genuinely distinct
candidate with overlapping naming must survive.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

TOKEN_RE = re.compile(r"[a-z0-9]+")
SUFFIX_RE = re.compile(
    r"(?:copy|fork|clone|renamed|rename|copy2|duplicate)(?:\d+)?$",
    re.IGNORECASE,
)
EXT_RE = re.compile(r"\.(?:js|mjs|cjs|ts|py|md)$", re.IGNORECASE)
JACCARD_FORK = 0.90


def tokenize(text: str) -> frozenset[str]:
    return frozenset(TOKEN_RE.findall((text or "").lower()))


def name_normalized(name: str) -> str:
    s = EXT_RE.sub("", name or "")
    parts = TOKEN_RE.findall(s.lower())
    while parts and SUFFIX_RE.fullmatch(parts[-1]):
        parts.pop()
    return "".join(parts)


def mechanisms_of(row: dict[str, Any]) -> tuple[str, ...]:
    raw = row.get("mechanisms") or []
    if isinstance(raw, str):
        raw = [raw]
    return tuple(sorted(str(x) for x in raw))


def does_tokens(row: dict[str, Any]) -> tuple[str, ...]:
    return tuple(sorted(tokenize(str(row.get("does") or ""))))


def fingerprint(row: dict[str, Any]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    return (mechanisms_of(row), does_tokens(row))


def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    union = sa | sb
    if not union:
        return 1.0
    return len(sa & sb) / len(union)


def bag(row: dict[str, Any]) -> frozenset[str]:
    return (
        tokenize(str(row.get("name") or ""))
        | tokenize(str(row.get("does") or ""))
        | frozenset(mechanisms_of(row))
    )


def is_renamed_copy(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """True when b is a renamed/trivial copy of a (or vice versa)."""
    if a.get("id") == b.get("id"):
        return False
    fp_a, fp_b = fingerprint(a), fingerprint(b)
    if fp_a == fp_b and (fp_a[0] or fp_a[1]):
        return True
    names_match = name_normalized(str(a.get("name") or "")) == name_normalized(
        str(b.get("name") or "")
    )
    if names_match and jaccard(tokenize(str(a.get("does") or "")), tokenize(str(b.get("does") or ""))) >= 0.80:
        return True
    if jaccard(bag(a), bag(b)) >= JACCARD_FORK:
        return True
    return False


class UnionFind:
    def __init__(self, ids: list[str]) -> None:
        self.parent = {i: i for i in ids}

    def find(self, x: str) -> str:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def _cluster(rows: list[dict[str, Any]], pair_fn) -> list[list[str]]:
    ids = [str(r["id"]) for r in rows]
    uf = UnionFind(ids)
    by_id = {str(r["id"]): r for r in rows}
    for i, a in enumerate(rows):
        for b in rows[i + 1 :]:
            if pair_fn(a, b):
                uf.union(str(a["id"]), str(b["id"]))
    groups: dict[str, list[str]] = {}
    for i in ids:
        groups.setdefault(uf.find(i), []).append(i)
    # Stable: keep lexicographically smallest id as representative.
    return [sorted(v) for v in groups.values()]


def fingerprint_clusters(rows: list[dict[str, Any]]) -> list[list[str]]:
    """Independent method A: exact mechanism+does fingerprint equality."""

    def pair(a: dict[str, Any], b: dict[str, Any]) -> bool:
        fa, fb = fingerprint(a), fingerprint(b)
        return fa == fb and bool(fa[0] or fa[1])

    return _cluster(rows, pair)


def jaccard_clusters(rows: list[dict[str, Any]]) -> list[list[str]]:
    """Independent method B: renamed-copy / high-Jaccard clustering."""
    return _cluster(rows, is_renamed_copy)


def discount(rows: list[dict[str, Any]], method: str = "jaccard") -> dict[str, Any]:
    clusters = fingerprint_clusters(rows) if method == "fingerprint" else jaccard_clusters(rows)
    kept = [min(c) for c in clusters]
    dropped = sorted({str(r["id"]) for r in rows} - set(kept))
    return {
        "method": method,
        "raw_count": len(rows),
        "discounted_count": len(kept),
        "dropped_ids": dropped,
        "clusters": clusters,
        "kept_ids": sorted(kept),
    }
