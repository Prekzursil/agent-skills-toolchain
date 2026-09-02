#!/usr/bin/env python3
"""Directional semantic diff of two typed workflows.

Aligns stages by mechanism kind (rename-invariant; identifiers are not the
alignment key). Emits typed ops for added/removed/changed stage, role, gate,
and tool. Classification is TWO-DIRECTIONAL: unique content on both sides is
DIVERGED, not a one-sided AHEAD verdict. That one-sided read is the measured
blind spot (31 data-loss-pointing misclassifications on this estate).

The diff is antisymmetric: reverse(diff(a,b)) equals diff(b,a).
"""
from __future__ import annotations

import copy
import json
from collections import Counter
from typing import Any

Verdict = str
OP_SWAP = {
    "added_stage": "removed_stage",
    "removed_stage": "added_stage",
    "added_role": "removed_role",
    "removed_role": "added_role",
    "added_gate": "removed_gate",
    "removed_gate": "added_gate",
    "added_tool": "removed_tool",
    "removed_tool": "added_tool",
    "added_edge": "removed_edge",
    "removed_edge": "added_edge",
    "changed_stage": "changed_stage",
    "changed_role": "changed_role",
    "changed_gate": "changed_gate",
    "changed_tool": "changed_tool",
}
VERDICT_SWAP = {
    "IDENTICAL": "IDENTICAL",
    "DIVERGED": "DIVERGED",
    "LEFT-AHEAD": "RIGHT-AHEAD",
    "RIGHT-AHEAD": "LEFT-AHEAD",
}


def canon(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): canon(obj[k]) for k in sorted(obj)}
    if isinstance(obj, (list, tuple)):
        return [canon(x) for x in obj]
    if isinstance(obj, set):
        return sorted((canon(x) for x in obj), key=lambda x: dumps(x))
    return obj


def dumps(obj: Any) -> str:
    return json.dumps(canon(obj), sort_keys=True, separators=(",", ":"))


def load_workflow(obj: Any) -> dict[str, Any]:
    if not isinstance(obj, dict):
        raise TypeError("workflow must be an object")
    stages = obj.get("stages") or []
    if not isinstance(stages, list):
        raise TypeError("stages must be a list")
    out_stages = []
    for i, raw in enumerate(stages):
        if not isinstance(raw, dict):
            raise TypeError(f"stage[{i}] must be an object")
        kind = str(raw.get("kind") or "")
        if not kind:
            raise ValueError(f"stage[{i}] missing kind")
        sid = str(raw.get("id") or f"stage-{i}")
        tools = raw.get("tools") or []
        if not isinstance(tools, list):
            raise TypeError(f"stage[{i}].tools must be a list")
        out_stages.append(
            {
                "id": sid,
                "kind": kind,
                "role": raw.get("role"),
                "gate": raw.get("gate"),
                "tools": [str(t) for t in tools],
                "inputs": list(raw.get("inputs") or []),
                "outputs": list(raw.get("outputs") or []),
            }
        )
    edges_in = obj.get("edges") or []
    edges: list[list[str]] = []
    if isinstance(edges_in, list):
        for e in edges_in:
            if isinstance(e, (list, tuple)) and len(e) == 2:
                edges.append([str(e[0]), str(e[1])])
    explicit = obj.get("roles")
    if explicit is None:
        roles = [s["role"] for s in out_stages if s.get("role")]
    else:
        roles = [str(r) for r in explicit]
    return {
        "id": str(obj.get("id") or ""),
        "stages": out_stages,
        "edges": edges,
        "roles": roles,
        "stopping": obj.get("stopping") or {},
    }


def stage_body(stage: dict[str, Any]) -> dict[str, Any]:
    """Rename-invariant body: identifiers are excluded."""
    return {
        "kind": stage["kind"],
        "role": stage.get("role"),
        "gate": canon(stage.get("gate")),
        "tools": sorted(str(t) for t in (stage.get("tools") or [])),
        "inputs": list(stage.get("inputs") or []),
        "outputs": list(stage.get("outputs") or []),
    }


def _lcs_align(a_keys: list[str], b_keys: list[str]) -> list[tuple[str, int | None, int | None]]:
    n, m = len(a_keys), len(b_keys)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            if a_keys[i] == b_keys[j]:
                dp[i][j] = 1 + dp[i + 1][j + 1]
            else:
                dp[i][j] = max(dp[i + 1][j], dp[i][j + 1])
    i = j = 0
    out: list[tuple[str, int | None, int | None]] = []
    while i < n and j < m:
        if a_keys[i] == b_keys[j]:
            out.append(("match", i, j))
            i += 1
            j += 1
        elif dp[i + 1][j] >= dp[i][j + 1]:
            out.append(("left", i, None))
            i += 1
        else:
            out.append(("right", None, j))
            j += 1
    while i < n:
        out.append(("left", i, None))
        i += 1
    while j < m:
        out.append(("right", None, j))
        j += 1
    return out


def _item(kind: str, **fields: Any) -> dict[str, Any]:
    row = {"kind": kind}
    row.update(fields)
    return row


def _op(op: str, **fields: Any) -> dict[str, Any]:
    row = {"op": op}
    row.update({k: v for k, v in fields.items() if v is not None})
    return row


def _payload_present(payload: Any) -> bool:
    if payload is None:
        return False
    if payload == [] or payload == {}:
        return False
    return True


def _unique_from_ops(ops: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    left: list[dict[str, Any]] = []
    right: list[dict[str, Any]] = []
    for op in ops:
        name = op["op"]
        if name.startswith("removed_"):
            payload = op.get("left")
            if _payload_present(payload):
                left.append(_item(name.removeprefix("removed_"), payload=payload))
        elif name.startswith("added_"):
            payload = op.get("right")
            if _payload_present(payload):
                right.append(_item(name.removeprefix("added_"), payload=payload))
        elif name.startswith("changed_"):
            lp, rp = op.get("left"), op.get("right")
            if _payload_present(lp):
                left.append(_item(name.removeprefix("changed_"), payload=lp))
            if _payload_present(rp):
                right.append(_item(name.removeprefix("changed_"), payload=rp))
    return left, right


def classify(left_unique: list, right_unique: list, *, one_directional: bool = False) -> Verdict:
    """Two-directional verdict, or the one-directional mutant (measured blind spot)."""
    if one_directional:
        if right_unique:
            return "RIGHT-AHEAD"
        if left_unique:
            return "LEFT-AHEAD"
        return "IDENTICAL"
    if left_unique and right_unique:
        return "DIVERGED"
    if left_unique:
        return "LEFT-AHEAD"
    if right_unique:
        return "RIGHT-AHEAD"
    return "IDENTICAL"


def _by_id(stages: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {s["id"]: s for s in stages}


def _edge_key(stages: list[dict[str, Any]], pair: list[str]) -> tuple[str, str] | None:
    idx = _by_id(stages)
    sa, sb = idx.get(pair[0]), idx.get(pair[1])
    if not sa or not sb:
        return None
    return (str(sa["kind"]), str(sb["kind"]))


def diff_workflows(
    left_raw: Any,
    right_raw: Any,
    *,
    one_directional: bool = False,
) -> dict[str, Any]:
    left = load_workflow(left_raw)
    right = load_workflow(right_raw)
    ls, rs = left["stages"], right["stages"]
    align = _lcs_align([s["kind"] for s in ls], [s["kind"] for s in rs])
    ops: list[dict[str, Any]] = []

    for tag, i, j in align:
        if tag == "left":
            st = ls[i]  # type: ignore[index]
            body = stage_body(st)
            ops.append(_op("removed_stage", stage_kind=st["kind"], left=body, left_id=st["id"]))
            if st.get("role"):
                ops.append(_op("removed_role", stage_kind=st["kind"], left=st["role"]))
            if st.get("gate") is not None:
                ops.append(_op("removed_gate", stage_kind=st["kind"], left=canon(st["gate"])))
            for t in st.get("tools") or []:
                ops.append(_op("removed_tool", stage_kind=st["kind"], left=t))
        elif tag == "right":
            st = rs[j]  # type: ignore[index]
            body = stage_body(st)
            ops.append(_op("added_stage", stage_kind=st["kind"], right=body, right_id=st["id"]))
            if st.get("role"):
                ops.append(_op("added_role", stage_kind=st["kind"], right=st["role"]))
            if st.get("gate") is not None:
                ops.append(_op("added_gate", stage_kind=st["kind"], right=canon(st["gate"])))
            for t in st.get("tools") or []:
                ops.append(_op("added_tool", stage_kind=st["kind"], right=t))
        else:
            a, b = ls[i], rs[j]  # type: ignore[index]
            ab, bb = stage_body(a), stage_body(b)
            if dumps(ab) != dumps(bb):
                ops.append(
                    _op(
                        "changed_stage",
                        stage_kind=a["kind"],
                        left=ab,
                        right=bb,
                        left_id=a["id"],
                        right_id=b["id"],
                    )
                )
            if a.get("role") != b.get("role"):
                ops.append(
                    _op(
                        "changed_role",
                        stage_kind=a["kind"],
                        left=a.get("role"),
                        right=b.get("role"),
                    )
                )
            if dumps(a.get("gate")) != dumps(b.get("gate")):
                ops.append(
                    _op(
                        "changed_gate",
                        stage_kind=a["kind"],
                        left=canon(a.get("gate")),
                        right=canon(b.get("gate")),
                    )
                )
            ta = Counter(a.get("tools") or [])
            tb = Counter(b.get("tools") or [])
            if ta != tb:
                only_l = sorted((ta - tb).elements())
                only_r = sorted((tb - ta).elements())
                if only_l and only_r:
                    ops.append(
                        _op(
                            "changed_tool",
                            stage_kind=a["kind"],
                            left=only_l,
                            right=only_r,
                        )
                    )
                for t in only_l:
                    ops.append(_op("removed_tool", stage_kind=a["kind"], left=t))
                for t in only_r:
                    ops.append(_op("added_tool", stage_kind=a["kind"], right=t))

    left_edges = Counter(k for e in left["edges"] if (k := _edge_key(ls, e)))
    right_edges = Counter(k for e in right["edges"] if (k := _edge_key(rs, e)))
    for k in sorted((left_edges - right_edges).elements()):
        ops.append(_op("removed_edge", left={"from_kind": k[0], "to_kind": k[1]}))
    for k in sorted((right_edges - left_edges).elements()):
        ops.append(_op("added_edge", right={"from_kind": k[0], "to_kind": k[1]}))

    left_unique, right_unique = _unique_from_ops(ops)
    verdict = classify(left_unique, right_unique, one_directional=one_directional)
    return {
        "left_id": left.get("id"),
        "right_id": right.get("id"),
        "verdict": verdict,
        "one_directional": one_directional,
        "ops": ops,
        "left_unique": left_unique,
        "right_unique": right_unique,
        "alignment": [{"tag": t, "left_index": i, "right_index": j} for t, i, j in align],
        "directional": True,
        "reports_both_sides_unique": True,
    }


def reverse_op(op: dict[str, Any]) -> dict[str, Any]:
    name = op["op"]
    if name not in OP_SWAP:
        raise KeyError(f"unreversible op {name}")
    new = copy.deepcopy(op)
    new["op"] = OP_SWAP[name]
    if "left" in new or "right" in new:
        new["left"], new["right"] = new.get("right"), new.get("left")
    if "left_id" in new or "right_id" in new:
        new["left_id"], new["right_id"] = new.get("right_id"), new.get("left_id")
    return {k: v for k, v in new.items() if v is not None}


def reverse_diff(doc: dict[str, Any]) -> dict[str, Any]:
    verdict = doc["verdict"]
    if verdict not in VERDICT_SWAP:
        raise KeyError(f"unreversible verdict {verdict}")
    ops = [reverse_op(op) for op in doc.get("ops") or []]
    align = []
    for row in doc.get("alignment") or []:
        tag = row.get("tag")
        if tag == "left":
            tag = "right"
        elif tag == "right":
            tag = "left"
        align.append(
            {
                "tag": tag,
                "left_index": row.get("right_index"),
                "right_index": row.get("left_index"),
            }
        )
    return {
        "left_id": doc.get("right_id"),
        "right_id": doc.get("left_id"),
        "verdict": VERDICT_SWAP[verdict],
        "one_directional": False,
        "ops": ops,
        "left_unique": copy.deepcopy(doc.get("right_unique") or []),
        "right_unique": copy.deepcopy(doc.get("left_unique") or []),
        "alignment": align,
        "directional": True,
        "reports_both_sides_unique": True,
    }


def _norm_op(op: dict[str, Any]) -> dict[str, Any]:
    return json.loads(dumps(op))


def canonical_diff(doc: dict[str, Any]) -> dict[str, Any]:
    """Stable form for equality: verdict + sorted ops + sorted unique lists."""
    ops = sorted((_norm_op(o) for o in doc.get("ops") or []), key=dumps)
    lu = sorted((_norm_op(x) for x in doc.get("left_unique") or []), key=dumps)
    ru = sorted((_norm_op(x) for x in doc.get("right_unique") or []), key=dumps)
    return {
        "verdict": doc.get("verdict"),
        "ops": ops,
        "left_unique": lu,
        "right_unique": ru,
        "left_id": doc.get("left_id"),
        "right_id": doc.get("right_id"),
    }


def diffs_equal(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return dumps(canonical_diff(a)) == dumps(canonical_diff(b))
