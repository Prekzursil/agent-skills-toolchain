#!/usr/bin/env python3
"""Precondition checker: (source pair, operator) -> LEGAL | ILLEGAL with a named edge.

Consumes the symmetrised compat relation, mechanism-conflict edges, and the
licence matrix. Operator-specific structural gates run only after those three
graphs have been consulted, so a licence refusal is recorded even when the
compat edge is present.
"""
from __future__ import annotations

from typing import Any

from world import World, edge_key, load_world

GENERIC_FORBIDDEN = frozenset(
    {
        "incompatible",
        "incompatibility",
        "illegal",
        "blocked",
        "no",
        "generic incompatibility",
    }
)


def _splice_ok(host: dict, donor: dict) -> bool:
    return donor["input_type"] in set(host["insertions"])


def check(
    left_id: str,
    right_id: str,
    operator: str,
    world: World | None = None,
) -> dict[str, Any]:
    w = world or load_world()
    if operator not in w.operators:
        edge = f"operator:{operator}"
        return _illegal(left_id, right_id, operator, edge, f"unknown operator {edge}")
    if left_id not in w.blueprints or right_id not in w.blueprints:
        missing = left_id if left_id not in w.blueprints else right_id
        edge = f"blueprint:{missing}"
        return _illegal(
            left_id, right_id, operator, edge, f"missing blueprint {edge}"
        )
    a = w.blueprints[left_id]
    b = w.blueprints[right_id]

    if not w.has_compat(left_id, right_id):
        edge = edge_key("compat", left_id, right_id)
        return _illegal(
            left_id,
            right_id,
            operator,
            edge,
            f"ILLEGAL missing symmetrised-compat edge {edge}",
        )

    lic = w.licence_cell(a["licence"], b["licence"])
    if lic["verdict"] != "ALLOW":
        edge = lic["edge"]
        return _illegal(
            left_id,
            right_id,
            operator,
            edge,
            (
                f"ILLEGAL licence-incompatible edge {edge} "
                f"(structural compat {edge_key('compat', left_id, right_id)} "
                f"is present and does not save the pair; {lic['note']})"
            ),
        )

    conf = w.conflict_edge(a["mechanisms"], b["mechanisms"])
    if conf:
        return _illegal(
            left_id,
            right_id,
            operator,
            conf,
            f"ILLEGAL mechanism-conflict edge {conf} co-locates mutually exclusive mechanisms",
        )

    extra = _operator_gate(a, b, operator)
    if extra is not None:
        edge, reason = extra
        return _illegal(left_id, right_id, operator, edge, reason)

    return {
        "left": left_id,
        "right": right_id,
        "operator": operator,
        "verdict": "LEGAL",
        "blocking_edge": None,
        "reason": f"LEGAL pair {edge_key('pair', left_id, right_id)} operator {operator}",
    }


def _operator_gate(a: dict, b: dict, operator: str) -> tuple[str, str] | None:
    if operator == "stage-splice":
        if not (_splice_ok(a, b) or _splice_ok(b, a)):
            edge = edge_key("type", a["input_type"] + "@" + a["id"], b["input_type"] + "@" + b["id"])
            return (
                edge,
                (
                    f"ILLEGAL stage-splice type-unsatisfied edge {edge} "
                    f"host insertions {a['id']}={a['insertions']} "
                    f"{b['id']}={b['insertions']}"
                ),
            )
    elif operator == "common-core":
        if a["family"] != b["family"]:
            edge = edge_key("family", a["family"], b["family"])
            return edge, f"ILLEGAL common-core family-mismatch edge {edge}"
        inter = sorted(set(a["stages"]) & set(b["stages"]))
        if not inter:
            edge = edge_key("stages", a["id"], b["id"])
            return (
                edge,
                f"ILLEGAL common-core empty-intersection edge {edge}",
            )
    elif operator == "best-of-breed":
        overlap = sorted(set(a["benchmarks"]) & set(b["benchmarks"]))
        if not overlap:
            edge = edge_key("slots", a["id"], b["id"])
            return edge, f"ILLEGAL best-of-breed no-scored-slot edge {edge}"
    elif operator == "ensemble":
        if a["output_type"] != b["output_type"]:
            edge = edge_key("output-type", a["output_type"], b["output_type"])
            return (
                edge,
                f"ILLEGAL ensemble output-type-mismatch edge {edge}",
            )
    elif operator == "conditional-hybrid":
        if not (a["predicates"] or b["predicates"] or a["default_branch"] or b["default_branch"]):
            edge = edge_key("predicate", a["id"], b["id"])
            return edge, f"ILLEGAL conditional-hybrid no-predicate edge {edge}"
    elif operator == "progressive":
        if a["cost"] == b["cost"]:
            edge = edge_key("cost", f"{a['cost']}@{a['id']}", f"{b['cost']}@{b['id']}")
            return edge, f"ILLEGAL progressive cost-tie edge {edge}"
    elif operator == "union":
        return None
    return None


def _illegal(
    left: str, right: str, operator: str, edge: str, reason: str
) -> dict[str, Any]:
    compact = reason.strip().lower()
    if compact in GENERIC_FORBIDDEN or "|" not in reason:
        raise AssertionError(
            f"reason must name a specific blocking edge, got {reason!r}"
        )
    if edge not in reason:
        reason = f"{reason} [edge {edge}]"
    return {
        "left": left,
        "right": right,
        "operator": operator,
        "verdict": "ILLEGAL",
        "blocking_edge": edge,
        "reason": reason,
    }


def cartesian(world: World | None = None) -> list[dict[str, Any]]:
    w = world or load_world()
    rows = []
    for left, right in w.pairs():
        for op in w.operators:
            rows.append(check(left, right, op, w))
    return rows


def legality_counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    per_op: dict[str, dict[str, int]] = {}
    for row in rows:
        slot = per_op.setdefault(row["operator"], {"LEGAL": 0, "ILLEGAL": 0})
        slot[row["verdict"]] += 1
    return {
        "per_operator": per_op,
        "LEGAL": sum(v["LEGAL"] for v in per_op.values()),
        "ILLEGAL": sum(v["ILLEGAL"] for v in per_op.values()),
        "cells": len(rows),
    }
