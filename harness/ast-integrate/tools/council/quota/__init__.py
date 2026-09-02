"""Council quota surface (IMP-0300 / IMP-0301).

``council.quota.targets`` evaluates every non-count target a CouncilSpec can
declare (coverage, category, novelty, diversity, objection, evidence,
counterexample) and defers ``unique_idea`` count targets to
``council.quota.unique_ideas``, the semantic-dedup unique-idea counter.
"""
from __future__ import annotations

from .targets import (
    COUNT_KINDS,
    KNOWN_KINDS,
    NON_COUNT_KINDS,
    SpecError,
    evaluate,
    evaluate_target,
)
from .unique_ideas import (
    JACCARD_THRESHOLD,
    cluster_ideas,
    naive_unique,
    unique_count_connected_components,
    unique_count_union_find,
)

__all__ = [
    "COUNT_KINDS",
    "JACCARD_THRESHOLD",
    "KNOWN_KINDS",
    "NON_COUNT_KINDS",
    "SpecError",
    "cluster_ideas",
    "evaluate",
    "evaluate_target",
    "naive_unique",
    "unique_count_connected_components",
    "unique_count_union_find",
]
