"""Shared transcript walking and Jaccard clustering.

Clustering is a helper, not the detector decision. Breadth (category
coverage) does not call cluster(). Detector (quota vs clusters) does.
"""
from __future__ import annotations

import re
from typing import Any

TOKEN_RE = re.compile(r"[a-z0-9]+")
JACCARD_DUP = 0.80


def tokens(text: str) -> frozenset[str]:
    return frozenset(TOKEN_RE.findall((text or "").lower()))


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def first_converge_index(events: list[dict]) -> int | None:
    for i, ev in enumerate(events):
        if ev.get("kind") == "converge":
            return i
    return None


def events_until(events: list[dict], end_exclusive: int | None) -> list[dict]:
    if end_exclusive is None:
        return list(events)
    return list(events[:end_exclusive])


def cluster_texts(texts: list[str], threshold: float = JACCARD_DUP) -> list[list[int]]:
    """Greedy clusters: assign each text to the first cluster whose medoid
    Jaccard is >= threshold. Returns lists of source indices."""
    bags = [tokens(t) for t in texts]
    clusters: list[list[int]] = []
    medoids: list[frozenset[str]] = []
    for i, bag in enumerate(bags):
        placed = False
        for c_i, med in enumerate(medoids):
            if jaccard(bag, med) >= threshold:
                clusters[c_i].append(i)
                placed = True
                break
        if not placed:
            clusters.append([i])
            medoids.append(bag)
    return clusters


def items_of_kind(events: list[dict], kind: str) -> list[dict]:
    return [e for e in events if e.get("kind") == kind]


def cluster_count(events: list[dict], kind: str) -> int:
    items = items_of_kind(events, kind)
    if not items:
        return 0
    return len(cluster_texts([str(e.get("text") or "") for e in items]))


def taxonomy_of(run: dict[str, Any]) -> list[str]:
    div = run.get("declared_divergence") or {}
    tax = div.get("taxonomy") or []
    return [str(x) for x in tax]


def idea_quota(run: dict[str, Any]) -> int:
    return int((run.get("declared_divergence") or {}).get("idea_quota") or 0)


def objection_quota(run: dict[str, Any]) -> int:
    return int((run.get("declared_divergence") or {}).get("objection_quota") or 0)
