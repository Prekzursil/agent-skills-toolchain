"""Structural mechanism fingerprint for a workflow (IMP-0170).

Hashes the TYPED STRUCTURE only: stage kinds, role sets, gate predicates,
tool classes and (optionally) the topology. Identifiers never enter the
hash: workflow id, stage ids, tool instance ids and titles are stripped;
stage references inside predicates are rewritten to $Sn after a
Weisfeiler-Lehman canonical order on coarse labels. Renaming everything
leaves the fingerprint unchanged; changing one gate predicate changes it.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _stage_rows(workflow: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in (workflow or {}).get("stages") or []:
        rows.append(
            {
                "id": str(raw.get("id") or ""),
                "kind": str(raw.get("kind") or "stage"),
                "title": raw.get("title"),
                "roles": sorted(str(r) for r in (raw.get("roles") or [])),
                "tools": sorted(
                    str(t.get("class") or t if isinstance(t, dict) else t)
                    for t in (raw.get("tools") or [])
                ),
                "tool_instances": sorted(
                    str(t.get("instance_id") or "")
                    for t in (raw.get("tools") or [])
                    if isinstance(t, dict)
                ),
                "gate": raw.get("gate"),
            }
        )
    return rows


def _edges(workflow: Any) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for e in (workflow or {}).get("edges") or []:
        out.append((str(e[0]), str(e[1])))
    return out


def _rewrite_refs(node: Any, refmap: dict[str, str]) -> Any:
    """Rewrite stage-id references inside a predicate to canonical $Sn form."""
    if isinstance(node, str):
        return refmap.get(node, node)
    if isinstance(node, list):
        return [_rewrite_refs(x, refmap) for x in node]
    if isinstance(node, tuple):
        return [_rewrite_refs(x, refmap) for x in node]
    if isinstance(node, dict):
        return {str(k): _rewrite_refs(v, refmap) for k, v in sorted(node.items())}
    return node


def fingerprint(workflow: Any, include_topology: bool = True) -> str:
    """Rename-invariant mechanism hash of the workflow structure."""
    rows = _stage_rows(workflow)
    edges = _edges(workflow) if include_topology else []
    ids = [r["id"] for r in rows]
    idset = set(ids)

    # Round-0 coarse labels: kind + roles + tool classes (predicate excluded:
    # it may reference raw ids, which must not leak into the canonical order).
    coarse = {
        r["id"]: _sha(_canonical(
            {"kind": r["kind"], "roles": r["roles"], "tools": r["tools"]}
        ))
        for r in rows
    }
    succs: dict[str, list[str]] = {i: [] for i in ids}
    for s, d in edges:
        if s in idset and d in idset:
            succs[s].append(d)
    labels = dict(coarse)
    for _round in range(2):
        nxt = {}
        for i in ids:
            nxt[i] = _sha(_canonical(
                {"self": labels[i], "succ": sorted(labels[s] for s in succs[i])}
            ))
        labels = nxt

    # Canonical order on refined labels; identical twins keep any stable order
    # (the hash is a bag, so twin permutations cannot change it).
    order = sorted(range(len(ids)), key=lambda k: (labels[ids[k]], coarse[ids[k]]))
    rank = {ids[order[pos]]: pos for pos in range(len(ids))}
    refmap = {sid: "$S" + str(rank[sid] + 1) for sid in ids if sid}

    final_labels = []
    for r in rows:
        gate_canon = _canonical(_rewrite_refs(r["gate"], refmap)) if r["gate"] is not None else "null"
        final_labels.append(_sha(_canonical({
            "kind": r["kind"],
            "roles": r["roles"],
            "tools": r["tools"],
            "gate": gate_canon,
        })))

    edge_pairs = sorted("$S" + str(rank[s] + 1) + "->" + "$S" + str(rank[d] + 1)
                        for s, d in edges if s in rank and d in rank)
    payload: dict[str, Any] = {"stages": sorted(final_labels)}
    if include_topology:
        payload["edges"] = edge_pairs
    return _sha(_canonical(payload))
