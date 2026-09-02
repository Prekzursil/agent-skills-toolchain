#!/usr/bin/env python3
"""RES-0165 unique-claim clustering — author union-find vs reviewer BFS.

Reuses tools.council.quota.unique_ideas so lexical merge is the same
instrument the estate already measures, not a second invented counter.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.quota.unique_ideas import (  # noqa: E402
    JACCARD_THRESHOLD,
    naive_unique,
    unique_count_connected_components,
    unique_count_union_find,
)

THRESHOLD = JACCARD_THRESHOLD


def _count(result: object) -> int:
    if isinstance(result, dict):
        return int(result.get("unique_count") or result.get("n") or 0)
    return int(result)


def author_unique(texts: list[str]) -> int:
    return _count(unique_count_union_find(texts, THRESHOLD))


def reviewer_unique(texts: list[str]) -> int:
    return _count(unique_count_connected_components(texts, THRESHOLD))


def string_unique(texts: list[str]) -> int:
    return naive_unique(texts)
