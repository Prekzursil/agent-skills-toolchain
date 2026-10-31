"""Set-valued semantic differ over two workflow IRs.

Per dimension, reports what one IR carries that the other does not.
ABSENT (id on one side only) is never collapsed into PRESENT-BUT-DIFFERENT
(same id, different payload). Order-insensitive dimensions are compared as
sets keyed by id, never as sequences.
"""
from __future__ import annotations

from typing import Any

from ir import DIMENSIONS, index_dimension, shuffled, validate_ir

KIND_ABSENT = "ABSENT"
KIND_CHANGED = "PRESENT-BUT-DIFFERENT"


def _row_absent(node_id: str, present_on: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": node_id,
        "kind": KIND_ABSENT,
        "present_on": present_on,
        "payload": payload,
    }


def _row_changed(
    node_id: str, left: dict[str, Any], right: dict[str, Any]
) -> dict[str, Any]:
    return {
        "id": node_id,
        "kind": KIND_CHANGED,
        "left": left,
        "right": right,
    }


def diff_dimension(
    left: dict[str, Any], right: dict[str, Any], dim: str
) -> dict[str, Any]:
    lmap = index_dimension(left, dim)
    rmap = index_dimension(right, dim)
    left_ids = set(lmap)
    right_ids = set(rmap)
    left_only = [
        _row_absent(i, "left", lmap[i]) for i in sorted(left_ids - right_ids)
    ]
    right_only = [
        _row_absent(i, "right", rmap[i]) for i in sorted(right_ids - left_ids)
    ]
    changed = [
        _row_changed(i, lmap[i], rmap[i])
        for i in sorted(left_ids & right_ids)
        if lmap[i] != rmap[i]
    ]
    return {
        "dimension": dim,
        "comparison": "set",
        "left_only": left_only,
        "right_only": right_only,
        "changed": changed,
        "empty": not (left_only or right_only or changed),
    }


def diff_irs(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    validate_ir(left)
    validate_ir(right)
    dims = [diff_dimension(left, right, d) for d in DIMENSIONS]
    return {
        "left_id": left["id"],
        "right_id": right["id"],
        "dimensions": dims,
        "empty": all(d["empty"] for d in dims),
        "comparison": "set-per-dimension",
    }


def signature(report: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    """Stable (dimension, kind, id, side) tuples for exact gold matching."""
    sig: list[tuple[str, str, str, str]] = []
    for dim in report["dimensions"]:
        d = dim["dimension"]
        for row in dim["left_only"]:
            sig.append((d, KIND_ABSENT, row["id"], "left"))
        for row in dim["right_only"]:
            sig.append((d, KIND_ABSENT, row["id"], "right"))
        for row in dim["changed"]:
            sig.append((d, KIND_CHANGED, row["id"], "both"))
    return sorted(sig)


def empty_report(report: dict[str, Any]) -> bool:
    return bool(report.get("empty")) and signature(report) == []


def self_diff(ir: dict[str, Any]) -> dict[str, Any]:
    return diff_irs(ir, ir)


def order_invariant(ir: dict[str, Any]) -> dict[str, Any]:
    return diff_irs(ir, shuffled(ir))


def sequence_decoy_diff(
    left: dict[str, Any], right: dict[str, Any], dim: str
) -> dict[str, Any]:
    """Broken control: zip nodes by list position. Must NOT match the real differ
    on a pair whose only difference is permutation of an order-insensitive dim.
    """
    from ir import COLLECTION

    lnodes = list(left.get(COLLECTION[dim]) or [])
    rnodes = list(right.get(COLLECTION[dim]) or [])
    n = max(len(lnodes), len(rnodes))
    left_only = []
    right_only = []
    changed = []
    for i in range(n):
        if i >= len(lnodes):
            right_only.append(
                _row_absent(rnodes[i]["id"], "right", {"seq_index": i})
            )
        elif i >= len(rnodes):
            left_only.append(
                _row_absent(lnodes[i]["id"], "left", {"seq_index": i})
            )
        elif lnodes[i].get("id") != rnodes[i].get("id"):
            changed.append(
                _row_changed(
                    f"seq[{i}]",
                    {"id": lnodes[i].get("id")},
                    {"id": rnodes[i].get("id")},
                )
            )
    return {
        "dimension": dim,
        "comparison": "sequence",
        "left_only": left_only,
        "right_only": right_only,
        "changed": changed,
        "empty": not (left_only or right_only or changed),
    }
