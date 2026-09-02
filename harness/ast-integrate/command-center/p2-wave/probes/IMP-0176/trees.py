#!/usr/bin/env python3
"""Typed predicate trees for component contracts (ANY/ALL/NOT/WEIGHTED/ATOM).

This is the IMP-0166-shaped grammar this unit consumes. Trees are JSON objects.
Prose fields on a component are not part of the grammar.
"""
from __future__ import annotations

from typing import Any, Mapping

OPS = frozenset({"ALL", "ANY", "NOT", "WEIGHTED", "ATOM"})
POLARITIES = frozenset({"require", "forbid"})
TREE_FIELDS = frozenset({"stop_tree", "tool_tree"})

# Values on these axes are pairwise exclusive when both are forced-require.
EXCLUSIVE_AXES: dict[str, frozenset[str]] = {
    "stop.quorum": frozenset({"unanimity", "majority", "plurality"}),
    "tool.network": frozenset({"egress", "airgap"}),
}


class TreeError(ValueError):
    pass


def _as_map(node: Any, loc: str) -> dict:
    if not isinstance(node, Mapping):
        raise TreeError(f"{loc}: expected object, got {type(node).__name__}")
    return dict(node)


def validate_tree(node: Any, loc: str = "tree") -> dict:
    n = _as_map(node, loc)
    op = n.get("op")
    if op not in OPS:
        raise TreeError(f"{loc}: unknown op {op!r}")
    if op == "ATOM":
        axis = n.get("axis")
        symbol = n.get("symbol")
        polarity = n.get("polarity")
        if not isinstance(axis, str) or not axis:
            raise TreeError(f"{loc}: ATOM.axis must be a non-empty string")
        if not isinstance(symbol, str) or not symbol:
            raise TreeError(f"{loc}: ATOM.symbol must be a non-empty string")
        if polarity not in POLARITIES:
            raise TreeError(f"{loc}: ATOM.polarity must be require|forbid")
        return n
    if op == "NOT":
        validate_tree(n.get("child"), f"{loc}.child")
        return n
    if op in {"ALL", "ANY"}:
        children = n.get("children")
        if not isinstance(children, list) or len(children) < 1:
            raise TreeError(f"{loc}: {op} needs a non-empty children list")
        for i, child in enumerate(children):
            validate_tree(child, f"{loc}.children[{i}]")
        return n
    # WEIGHTED
    children = n.get("children")
    threshold = n.get("threshold")
    if not isinstance(children, list) or len(children) < 1:
        raise TreeError(f"{loc}: WEIGHTED needs a non-empty children list")
    if not isinstance(threshold, (int, float)):
        raise TreeError(f"{loc}: WEIGHTED.threshold must be numeric")
    total = 0.0
    for i, row in enumerate(children):
        r = _as_map(row, f"{loc}.children[{i}]")
        w = r.get("weight")
        if not isinstance(w, (int, float)) or w < 0:
            raise TreeError(f"{loc}.children[{i}]: weight must be >= 0")
        total += float(w)
        validate_tree(r.get("tree"), f"{loc}.children[{i}].tree")
    if float(threshold) > total + 1e-12:
        raise TreeError(f"{loc}: threshold {threshold} exceeds total weight {total}")
    return n


def component_trees(component: Mapping[str, Any]) -> tuple[dict, dict]:
    """Return (stop_tree, tool_tree). Ignores every other field."""
    stop = validate_tree(component.get("stop_tree"), "stop_tree")
    tool = validate_tree(component.get("tool_tree"), "tool_tree")
    return stop, tool
