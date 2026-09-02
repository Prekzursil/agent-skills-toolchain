#!/usr/bin/env python3
"""Structural conflict detection over predicate trees.

Reads only stop_tree and tool_tree. Forced atoms are computed by walking
ALL/ANY/NOT/WEIGHTED/ATOM. Keyword matching on prose is not used.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from trees import EXCLUSIVE_AXES, TREE_FIELDS, TreeError, component_trees, validate_tree


def _forced_atoms(node: Mapping[str, Any]) -> set[tuple[str, str, str]]:
    """Return forced (axis, symbol, polarity) triples."""
    op = node["op"]
    if op == "ATOM":
        return {(node["axis"], node["symbol"], node["polarity"])}
    if op == "NOT":
        child = _forced_atoms(node["child"])
        flipped = set()
        for axis, symbol, polarity in child:
            flipped.add(
                (axis, symbol, "forbid" if polarity == "require" else "require")
            )
        return flipped
    if op == "ALL":
        out: set[tuple[str, str, str]] = set()
        for child in node["children"]:
            out |= _forced_atoms(child)
        return out
    if op == "ANY":
        sets = [_forced_atoms(c) for c in node["children"]]
        if not sets:
            return set()
        return set.intersection(*sets)
    # WEIGHTED: a child is forced when omitting it makes the threshold unreachable.
    rows = node["children"]
    total = sum(float(r["weight"]) for r in rows)
    threshold = float(node["threshold"])
    out = set()
    for row in rows:
        if float(row["weight"]) > total - threshold + 1e-12:
            out |= _forced_atoms(row["tree"])
    return out


def _self_conflicts(atoms: set[tuple[str, str, str]]) -> list[dict]:
    hits: list[dict] = []
    by_key: dict[tuple[str, str], set[str]] = {}
    for axis, symbol, polarity in atoms:
        by_key.setdefault((axis, symbol), set()).add(polarity)
    for (axis, symbol), pols in sorted(by_key.items()):
        if "require" in pols and "forbid" in pols:
            hits.append(
                {
                    "code": "INTERNAL_POLARITY",
                    "axis": axis,
                    "symbol": symbol,
                }
            )
    required = [(a, s) for a, s, p in atoms if p == "require"]
    for i, (a1, s1) in enumerate(required):
        excl = EXCLUSIVE_AXES.get(a1)
        if not excl:
            continue
        for a2, s2 in required[i + 1 :]:
            if a1 == a2 and s1 != s2 and s1 in excl and s2 in excl:
                hits.append(
                    {
                        "code": "INTERNAL_EXCLUSIVE",
                        "axis": a1,
                        "symbols": sorted([s1, s2]),
                    }
                )
    return hits


def tree_is_individually_valid(node: Mapping[str, Any]) -> tuple[bool, list[dict]]:
    try:
        validate_tree(node)
    except TreeError as exc:
        return False, [{"code": "MALFORMED", "detail": str(exc)}]
    hits = _self_conflicts(_forced_atoms(node))
    return (not hits), hits


def _pair_conflicts(
    left: set[tuple[str, str, str]], right: set[tuple[str, str, str]]
) -> list[dict]:
    hits: list[dict] = []
    for a1, s1, p1 in sorted(left):
        for a2, s2, p2 in sorted(right):
            if a1 == a2 and s1 == s2 and p1 != p2:
                hits.append(
                    {
                        "code": "POLARITY",
                        "axis": a1,
                        "symbol": s1,
                        "left_polarity": p1,
                        "right_polarity": p2,
                    }
                )
            if (
                a1 == a2
                and s1 != s2
                and p1 == "require"
                and p2 == "require"
            ):
                excl = EXCLUSIVE_AXES.get(a1)
                if excl and s1 in excl and s2 in excl:
                    hits.append(
                        {
                            "code": "EXCLUSIVE",
                            "axis": a1,
                            "left_symbol": s1,
                            "right_symbol": s2,
                        }
                    )
    return hits


def detect_trees(
    left_stop: Mapping[str, Any],
    left_tool: Mapping[str, Any],
    right_stop: Mapping[str, Any],
    right_tool: Mapping[str, Any],
) -> dict:
    ls, lt = _forced_atoms(left_stop), _forced_atoms(left_tool)
    rs, rt = _forced_atoms(right_stop), _forced_atoms(right_tool)
    stop_hits = _pair_conflicts(ls, rs)
    tool_hits = _pair_conflicts(lt, rt)
    return {
        "conflict": bool(stop_hits or tool_hits),
        "stop": stop_hits,
        "tool": tool_hits,
        "left_forced_stop": sorted(ls),
        "left_forced_tool": sorted(lt),
        "right_forced_stop": sorted(rs),
        "right_forced_tool": sorted(rt),
    }


def detect_pair(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict:
    l_stop, l_tool = component_trees(left)
    r_stop, r_tool = component_trees(right)
    result = detect_trees(l_stop, l_tool, r_stop, r_tool)
    result["left_id"] = left.get("id")
    result["right_id"] = right.get("id")
    return result


def individually_valid_component(component: Mapping[str, Any]) -> tuple[bool, dict]:
    stop, tool = component_trees(component)
    sok, shits = tree_is_individually_valid(stop)
    tok, thits = tree_is_individually_valid(tool)
    return sok and tok, {"stop": shits, "tool": thits}


def scan_pairs(components: Iterable[Mapping[str, Any]]) -> list[dict]:
    rows = list(components)
    out: list[dict] = []
    for i, left in enumerate(rows):
        for right in rows[i + 1 :]:
            out.append(detect_pair(left, right))
    return out


# TREE_FIELDS is imported so callers can name the only maps this module walks.
assert TREE_FIELDS == frozenset({"stop_tree", "tool_tree"})
