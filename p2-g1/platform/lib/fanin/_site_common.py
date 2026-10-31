"""Shared reduce_unit body for every fan-in site.

Each site module re-exports the SAME ``evaluate`` object (identity, not a copy)
and funnels its unit reduction through it. A site never computes its own
completion verdict.
"""
from __future__ import annotations

from typing import Any

from completion_predicate import PredicateResult, evaluate


def reduce_unit(receipt: Any, **kwargs: Any) -> PredicateResult:
    """Reduce one unit's receipt through the shared twelve-condition judge."""
    return evaluate(receipt, **kwargs)


__all__ = ["evaluate", "reduce_unit"]
