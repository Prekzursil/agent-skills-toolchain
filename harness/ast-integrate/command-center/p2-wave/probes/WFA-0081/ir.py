"""Fusion IR construction check for a blueprint pair.

Declared compatibility that cannot be constructed is not compatibility.
A HARD mechanism conflict makes the pair unsatisfiable; SOFT does not.
"""
from __future__ import annotations

from typing import Any

from maplib import HARD_MECH_PAIRS, canon_pair

OPERATOR_BARRIER = "parallel-barrier"
OPERATOR_SEQUENCE = "sequence-join"


def conflict_on(mechs_a: set[str], mechs_b: set[str]) -> tuple[str, str] | None:
    for m1, m2 in HARD_MECH_PAIRS:
        if (m1 in mechs_a and m2 in mechs_b) or (m2 in mechs_a and m1 in mechs_b):
            return (m1, m2)
    return None


def operator_for(mechs_a: set[str], mechs_b: set[str]) -> str:
    barrierish = {
        "mech.blocking-fan-in",
        "mech.fire-and-forget",
        "mech.wide-fan-out",
        "mech.strict-topo-order",
    }
    if (mechs_a | mechs_b) & barrierish:
        return OPERATOR_BARRIER
    return OPERATOR_SEQUENCE


def construct_fusion(node_a: dict[str, Any], node_b: dict[str, Any]) -> dict[str, Any]:
    a, b = node_a["id"], node_b["id"]
    lo, hi = canon_pair(a, b)
    mechs_a = set(node_a.get("mechanisms") or [])
    mechs_b = set(node_b.get("mechanisms") or [])
    hit = conflict_on(mechs_a, mechs_b)
    if hit is not None:
        return {
            "pair": [lo, hi],
            "expressible": False,
            "reason": f"HARD conflict {hit[0]} vs {hit[1]} yields an unsatisfiable IR",
            "conflicting_mechanisms": list(hit),
            "ir": None,
        }
    stages_a = list(node_a.get("stages") or [])
    stages_b = list(node_b.get("stages") or [])
    if not stages_a or not stages_b:
        return {
            "pair": [lo, hi],
            "expressible": False,
            "reason": "a source has no stages; fusion would invent structure",
            "ir": None,
        }
    op = operator_for(mechs_a, mechs_b)
    join_id = f"fusion.{lo}+{hi}.join"
    join_stage = {
        "id": join_id,
        "kind": "fan-in-barrier" if op == OPERATOR_BARRIER else "sequence-join",
        "anchor": f"fusion:{lo}+{hi}:join",
        "waits_for": [stages_a[-1]["id"], stages_b[-1]["id"]],
    }
    ir = {
        "id": f"fusion.{lo}+{hi}",
        "kind": "WorkflowIR",
        "operator": op,
        "sources": [lo, hi],
        "stages": stages_a + stages_b + [join_stage],
        "gates": [
            {
                "id": f"fusion.{lo}+{hi}.lineage-gate",
                "kind": "lineage-closed",
                "anchor": f"fusion:{lo}+{hi}:gate",
            }
        ],
        "roles": ["fusion-composer"],
        "lineage": {
            "decomposes_to": [lo, hi],
            "merges_executed": 0,
        },
        "execution_semantics": None,
        "note": "IR only; not a second execution runtime. No merge has been executed.",
    }
    recovered = list(ir["lineage"]["decomposes_to"])
    if recovered != [lo, hi]:
        return {
            "pair": [lo, hi],
            "expressible": False,
            "reason": "lineage round-trip failed",
            "ir": ir,
        }
    return {
        "pair": [lo, hi],
        "expressible": True,
        "reason": f"fusion of pair type {op} is expressible in WorkflowIR",
        "operator": op,
        "ir": ir,
        "decomposes_to": recovered,
    }
