#!/usr/bin/env python3
"""Token-set Jaccard near-duplicate instrument (IMP-0171).

This is a LEXICAL instrument: lowercase [a-z0-9]+ token sets, Jaccard
|A∩B|/|A∪B|. It does not embed, align, or interpret meaning. A full
semantic rewrite of the same mechanism is therefore NOT detectable: it
lands in the same score band as a genuinely distinct candidate.
"""
from __future__ import annotations

import re
from typing import Iterable

TOKEN_RE = re.compile(r"[a-z0-9]+")
SCOPE = (
    "This instrument is LEXICAL only (token-set Jaccard over candidate text). "
    "A full semantic rewrite is NOT detectable by this instrument: it lands "
    "in the same score band as a genuinely distinct pair. Near-duplicate "
    "verdicts apply only to lexical similarity (exact rename, vocabulary-"
    "retaining paraphrase, one-parameter fork). They are not mechanism "
    "identity and must not be read as such."
)


def tokenize(text: str) -> frozenset[str]:
    return frozenset(TOKEN_RE.findall((text or "").lower()))


def jaccard(a: str, b: str) -> float:
    """Token-set Jaccard in [0, 1]. Empty-empty is 1.0; one-empty is 0.0."""
    left, right = tokenize(a), tokenize(b)
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def score_pair(left_id: str, left: str, right_id: str, right: str) -> dict:
    ja = round(jaccard(left, right), 6)
    ta, tb = tokenize(left), tokenize(right)
    return {
        "left_id": left_id,
        "right_id": right_id,
        "jaccard": ja,
        "left_token_count": len(ta),
        "right_token_count": len(tb),
        "intersection": len(ta & tb),
        "union": len(ta | tb),
    }


def pairwise_scan(candidates: Iterable[tuple[str, str]]) -> list[dict]:
    """Full pairwise token-Jaccard scan. Pair ids are ordered lexicographically."""
    rows = [(str(i), str(t)) for i, t in candidates]
    out: list[dict] = []
    for i, (lid, lt) in enumerate(rows):
        for rid, rt in rows[i + 1 :]:
            if lid <= rid:
                out.append(score_pair(lid, lt, rid, rt))
            else:
                out.append(score_pair(rid, rt, lid, lt))
    out.sort(key=lambda r: (-r["jaccard"], r["left_id"], r["right_id"]))
    return out


def above_threshold(scan: list[dict], threshold: float) -> list[dict]:
    return [r for r in scan if r["jaccard"] >= threshold]
