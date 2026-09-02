#!/usr/bin/env python3
"""New capability router for IMP-0400 (pinned lexical model).

Deterministic stemmed-Jaccard over query vs (triggers + description + id).
Capabilities below THRESHOLD are dropped (typed no-fit), so negative queries
do not get a popularity pad. Tie-break is capability id, never random.
"""
from __future__ import annotations

import re
from typing import Any

PINNED_MODEL_ID = "imp0400-lexical-jaccard-v1"
THRESHOLD = 0.18
_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = frozenset(
    {
        "the",
        "a",
        "an",
        "to",
        "of",
        "and",
        "for",
        "in",
        "on",
        "is",
        "by",
        "with",
        "from",
        "this",
        "that",
        "must",
        "into",
        "over",
        "than",
        "its",
        "are",
        "be",
        "or",
        "at",
        "as",
        "it",
        "do",
        "how",
        "i",
        "my",
        "now",
        "then",
    }
)


def stem(tok: str) -> str:
    if len(tok) > 4 and tok.endswith("es"):
        return tok[:-2]
    if len(tok) > 3 and tok.endswith("s"):
        return tok[:-1]
    return tok


def tokens(text: str) -> frozenset[str]:
    out: set[str] = set()
    for raw in _TOKEN.findall(text.lower()):
        if raw in _STOP or len(raw) < 3:
            continue
        out.add(stem(raw))
    return frozenset(out)


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if inter == 0:
        return 0.0
    return inter / len(a | b)


def cap_tokens(cap: dict[str, Any]) -> frozenset[str]:
    parts = [
        str(cap.get("id") or "").replace("_", " ").replace(".", " "),
        " ".join(str(t) for t in (cap.get("triggers") or [])),
        str(cap.get("description") or ""),
    ]
    return tokens(" ".join(parts))


def score_query(query: str, cap: dict[str, Any]) -> float:
    return jaccard(tokens(query), cap_tokens(cap))


def router_select(
    query: str,
    capabilities: list[dict[str, Any]],
    k: int,
    threshold: float = THRESHOLD,
) -> list[str]:
    ranked: list[tuple[float, str]] = []
    for cap in capabilities:
        s = score_query(query, cap)
        if s >= threshold:
            ranked.append((s, str(cap["id"])))
    ranked.sort(key=lambda t: (-t[0], t[1]))
    return [cid for _s, cid in ranked[:k]]
