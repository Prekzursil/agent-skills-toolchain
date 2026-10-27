"""IMP-0171: token-Jaccard lexical near-duplicate scorer."""
from __future__ import annotations

import re

_WORD_RE = re.compile(r"[a-z0-9]+")


def tokens(text: str) -> set:
    return set(_WORD_RE.findall(text.lower()))


def jaccard(a: str, b: str) -> dict:
    ta, tb = tokens(a), tokens(b)
    inter = len(ta & tb)
    union = len(ta | tb)
    return {
        "jaccard": (inter / union) if union else 0.0,
        "intersection": inter,
        "union": union,
    }


def score_pair(a: str, b: str) -> float:
    return jaccard(a, b)["jaccard"]
