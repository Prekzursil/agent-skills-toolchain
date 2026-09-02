"""Frozen idea bags for CNL-0054. Same raw count n=24 on clustered, spread, token."""
from __future__ import annotations

from typing import Any

TAXONOMY_IDS = [
    "mechanism",
    "interface",
    "verification",
    "failure-mode",
    "economics",
    "governance",
    "security",
    "operability",
]

N = 24


def _bag(prefix: str, spec: list[tuple[str, int]]) -> list[dict[str, Any]]:
    ideas: list[dict[str, Any]] = []
    n = 1
    for cat, count in spec:
        for k in range(count):
            ideas.append(
                {
                    "id": f"{prefix}{n:02d}",
                    "category": cat,
                    "text": f"{prefix.lower()}-{cat}-{k+1}",
                }
            )
            n += 1
    return ideas


def spread() -> list[dict[str, Any]]:
    """Genuine spread: 3 ideas in each of 8 declared categories (n=24)."""
    return _bag("S", [(c, 3) for c in TAXONOMY_IDS])


def clustered() -> list[dict[str, Any]]:
    """Planted-bad: all 24 ideas in exactly 2 categories."""
    return _bag("C", [("mechanism", 12), ("interface", 12)])


def token_coverage() -> list[dict[str, Any]]:
    """Coverage-gamed: one idea in every category, remainder dumped into mechanism."""
    spec = [("mechanism", 17)] + [(c, 1) for c in TAXONOMY_IDS if c != "mechanism"]
    return _bag("T", spec)


def invalid_label() -> list[dict[str, Any]]:
    """Negative: spread bag with one out-of-taxonomy label."""
    ideas = spread()
    ideas[0] = {
        "id": "X01",
        "category": "popular",
        "text": "out-of-taxonomy-popular",
    }
    return ideas


def assert_counts() -> None:
    s, c, t = spread(), clustered(), token_coverage()
    if len(s) != N or len(c) != N or len(t) != N:
        raise AssertionError(f"count mismatch {[len(s), len(c), len(t)]}")
    if {i["category"] for i in c} != {"mechanism", "interface"}:
        raise AssertionError("clustered is not 2-category")
    if {i["category"] for i in s} != set(TAXONOMY_IDS):
        raise AssertionError("spread does not hit every declared category")
    if {i["category"] for i in t} != set(TAXONOMY_IDS):
        raise AssertionError("token_coverage does not hit every declared category")
