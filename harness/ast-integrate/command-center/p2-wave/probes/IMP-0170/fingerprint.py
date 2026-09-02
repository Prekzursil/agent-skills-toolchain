#!/usr/bin/env python3
"""Structural mechanism fingerprint for a typed workflow.

The digest covers stage kinds, the role set, gate predicates, tool classes,
and topology. Identifiers (workflow id, stage ids, tool instance ids, titles)
are stripped. Gate predicates live on topology (stage-exit conditions and
edge conditions), so dropping topology drops the gates: a gate-mutation
test that is green on the full fingerprint goes red on the stripped hasher.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

FingerprintHex = str


def _dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_hex(obj: Any) -> FingerprintHex:
    return hashlib.sha256(_dumps(obj).encode("utf-8")).hexdigest()


def _sorted_unique(xs: Iterable[Any]) -> list[Any]:
    return sorted(set(xs))


def canon_predicate(pred: Any, id_map: dict[str, str] | None = None) -> Any:
    """Canonical predicate tree. ALL/ANY arguments commute. Stage references
    are rewritten through id_map (rename invariance)."""
    if pred is None:
        return None
    if not isinstance(pred, dict):
        return pred
    id_map = id_map or {}
    if "atom" in pred:
        out: dict[str, Any] = {"atom": pred["atom"]}
        if "stage" in pred:
            sid = pred["stage"]
            out["stage"] = id_map.get(str(sid), sid)
        if "role" in pred:
            out["role"] = pred["role"]
        params = pred.get("params")
        if params is not None:
            if isinstance(params, dict):
                out["params"] = {k: params[k] for k in sorted(params)}
            else:
                out["params"] = params
        return out
    op = pred.get("op")
    if op == "NOT":
        inner = pred.get("arg", pred.get("args"))
        if isinstance(inner, list) and len(inner) == 1:
            inner = inner[0]
        return {"op": "NOT", "arg": canon_predicate(inner, id_map)}
    if op in ("ALL", "ANY"):
        args = [canon_predicate(a, id_map) for a in (pred.get("args") or [])]
        args.sort(key=_dumps)
        return {"op": op, "args": args}
    if op == "WEIGHTED":
        weighted = []
        for item in pred.get("args") or []:
            if isinstance(item, dict) and "pred" in item:
                weighted.append(
                    {
                        "pred": canon_predicate(item["pred"], id_map),
                        "weight": item.get("weight", 1),
                    }
                )
            else:
                weighted.append({"pred": canon_predicate(item, id_map), "weight": 1})
        weighted.sort(key=_dumps)
        return {
            "op": "WEIGHTED",
            "args": weighted,
            "threshold": pred.get("threshold", 1),
        }
    rest = {k: pred[k] for k in sorted(pred) if k != "op"}
    rewritten = {}
    for k, v in rest.items():
        if isinstance(v, dict):
            rewritten[k] = canon_predicate(v, id_map)
        elif isinstance(v, list):
            rewritten[k] = [
                canon_predicate(i, id_map) if isinstance(i, dict) else i for i in v
            ]
        else:
            rewritten[k] = v
    return {"op": op, **rewritten}


def _tool_classes(stage: dict) -> list[str]:
    classes: list[str] = []
    for t in stage.get("tools") or []:
        if isinstance(t, str):
            classes.append(t)
        elif isinstance(t, dict):
            classes.append(
                str(t.get("class") or t.get("kind") or t.get("type") or "UNKNOWN")
            )
        else:
            classes.append(str(t))
    return _sorted_unique(classes)


def _role_set(stage: dict) -> list[str]:
    out: list[str] = []
    for r in stage.get("roles") or []:
        if isinstance(r, str):
            out.append(r)
        elif isinstance(r, dict):
            out.append(str(r.get("type") or r.get("kind") or r.get("role") or "UNKNOWN"))
        else:
            out.append(str(r))
    return _sorted_unique(out)


def _stages(wf: dict) -> list[dict]:
    return list(wf.get("stages") or wf.get("nodes") or [])


def _edges(wf: dict) -> list[dict]:
    return list(wf.get("edges") or wf.get("topology") or [])


def _coarse_label(stage: dict) -> dict:
    return {
        "kind": stage.get("kind") or stage.get("type") or "UNKNOWN",
        "roles": _role_set(stage),
        "tools": _tool_classes(stage),
    }


def _adjacency(
    n: int, edges: list[tuple[int, int, Any]]
) -> tuple[list[list[tuple[int, Any]]], list[list[tuple[int, Any]]]]:
    pred: list[list[tuple[int, Any]]] = [[] for _ in range(n)]
    succ: list[list[tuple[int, Any]]] = [[] for _ in range(n)]
    for frm, to, gate in edges:
        succ[frm].append((to, gate))
        pred[to].append((frm, gate))
    return pred, succ


def _wl_colors(node_labels: list[Any], edges: list[tuple[int, int, Any]]) -> list[str]:
    n = len(node_labels)
    colors = [_dumps(lab) for lab in node_labels]
    pred, succ = _adjacency(n, edges)
    for _ in range(max(n, 1)):
        nxt = []
        for i in range(n):
            incoming = tuple(sorted((colors[j], _dumps(g)) for j, g in pred[i]))
            outgoing = tuple(sorted((colors[j], _dumps(g)) for j, g in succ[i]))
            nxt.append(_dumps((colors[i], incoming, outgoing)))
        if nxt == colors:
            break
        colors = nxt
    return colors


def _canonical_order(
    node_labels: list[Any],
    colors: list[str],
    edges: list[tuple[int, int, Any]],
    *,
    use_graph: bool,
) -> list[int]:
    n = len(node_labels)
    if n == 0:
        return []
    if not use_graph:
        return sorted(range(n), key=lambda i: (_dumps(node_labels[i]), i))
    _pred, succ = _adjacency(n, edges)
    remaining = set(range(n))
    order: list[int] = []

    def start_pick() -> int:
        return min(remaining, key=lambda i: (colors[i], _dumps(node_labels[i]), i))

    while remaining:
        stack = [start_pick()]
        while stack:
            i = stack.pop()
            if i not in remaining:
                continue
            remaining.remove(i)
            order.append(i)
            nbrs = [j for j, _ in succ[i] if j in remaining]
            nbrs.sort(key=lambda j: (colors[j], _dumps(node_labels[j]), j))
            stack.extend(reversed(nbrs))
    return order


def structural_payload(wf: dict, *, include_topology: bool = True) -> dict:
    """Rename-invariant payload. Gates are stored only inside topology."""
    stages = _stages(wf)
    raw_ids = [str(s.get("id") or s.get("name") or f"anon{i}") for i, s in enumerate(stages)]
    id_to_pos = {sid: i for i, sid in enumerate(raw_ids)}
    coarse = [_coarse_label(s) for s in stages]

    edge_triples: list[tuple[int, int, Any]] = []
    for e in _edges(wf):
        frm = e.get("from") or e.get("src") or e.get("source")
        to = e.get("to") or e.get("dst") or e.get("target")
        if frm not in id_to_pos or to not in id_to_pos:
            continue
        edge_triples.append((id_to_pos[str(frm)], id_to_pos[str(to)], e.get("gate")))

    role_set = _sorted_unique(r for s in stages for r in _role_set(s))
    tool_classes = _sorted_unique(t for s in stages for t in _tool_classes(s))

    if not include_topology:
        order = _canonical_order(
            coarse, [_dumps(x) for x in coarse], [], use_graph=False
        )
        return {
            "role_set": role_set,
            "stage_kinds": [coarse[old]["kind"] for old in order],
            "tool_classes": tool_classes,
        }

    # Color by coarse labels + connectivity only (no raw ids, no gates).
    shape_edges = [(frm, to, None) for frm, to, _gate in edge_triples]
    colors = _wl_colors(coarse, shape_edges)
    order = _canonical_order(coarse, colors, shape_edges, use_graph=True)
    pos_to_canon = {old: new for new, old in enumerate(order)}
    id_map = {raw_ids[old]: f"$S{pos_to_canon[old]}" for old in range(len(raw_ids))}

    canon_nodes = []
    for new, old in enumerate(order):
        lab = dict(coarse[old])
        lab["gate"] = canon_predicate(stages[old].get("gate"), id_map)
        lab["i"] = new
        canon_nodes.append(lab)
    canon_edges = [
        {
            "from": pos_to_canon[frm],
            "to": pos_to_canon[to],
            "gate": canon_predicate(gate, id_map),
        }
        for frm, to, gate in edge_triples
    ]
    canon_edges.sort(key=_dumps)
    return {
        "role_set": role_set,
        "stage_kinds": [coarse[old]["kind"] for old in order],
        "tool_classes": tool_classes,
        "topology": {"edges": canon_edges, "nodes": canon_nodes},
    }


structural_payload = structural_payload


def fingerprint(wf: dict, *, include_topology: bool = True) -> FingerprintHex:
    return _sha256_hex(structural_payload(wf, include_topology=include_topology))


def fingerprints_equal(a: dict, b: dict, *, include_topology: bool = True) -> bool:
    return fingerprint(a, include_topology=include_topology) == fingerprint(
        b, include_topology=include_topology
    )
