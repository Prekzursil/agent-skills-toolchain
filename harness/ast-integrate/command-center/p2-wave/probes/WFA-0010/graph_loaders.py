#!/usr/bin/env python3
"""Graph loaders that consume the WFA-0010 id migration map.

Id tokens on provenance and compat edges are resolved through alias rows
before endpoint lookup. A rename that does not emit an alias row is therefore
visible as a dangling reference rather than a silent orphan. Documentation
alone cannot satisfy this module: load_provenance and load_compat call resolve.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

AliasMap = Mapping[str, str]


def alias_map_from_rows(rows: Iterable[Mapping[str, Any]] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in rows or []:
        src = str(row.get("from") or row.get("alias") or "").strip()
        dst = str(row.get("to") or row.get("canonical") or "").strip()
        if src and dst:
            out[src] = dst
    return out


def resolve(token: str, aliases: AliasMap | None) -> str:
    """Follow alias rows until a current id. Identity rows (from==to) halt."""
    cur = str(token or "")
    if not aliases:
        return cur
    seen: list[str] = []
    while cur in aliases and aliases[cur] != cur:
        if cur in seen:
            raise ValueError("alias cycle: " + " -> ".join(seen + [cur]))
        seen.append(cur)
        cur = str(aliases[cur])
    return cur


def _endpoints(edge: Mapping[str, Any]) -> tuple[str, str]:
    a = edge.get("src") or edge.get("source") or edge.get("from") or edge.get("a")
    b = edge.get("dst") or edge.get("target") or edge.get("to") or edge.get("b")
    return str(a or ""), str(b or "")


def load_provenance(
    edges: Iterable[Mapping[str, Any]],
    record_ids: Iterable[str],
    aliases: AliasMap | None,
    *,
    apply_map: bool,
) -> dict[str, Any]:
    """Resolve provenance edge endpoints through the migration map when asked."""
    live = {str(i) for i in record_ids}
    resolved_edges: list[dict[str, str]] = []
    dangling: list[dict[str, str]] = []
    for edge in edges:
        raw_a, raw_b = _endpoints(edge)
        a = resolve(raw_a, aliases) if apply_map else raw_a
        b = resolve(raw_b, aliases) if apply_map else raw_b
        row = {
            "src": a,
            "dst": b,
            "raw_src": raw_a,
            "raw_dst": raw_b,
        }
        missing = [n for n in (a, b) if n not in live]
        if missing:
            dangling.append({**row, "missing": ",".join(missing)})
        else:
            resolved_edges.append(row)
    return {
        "kind": "provenance",
        "apply_map": apply_map,
        "resolved": resolved_edges,
        "dangling": dangling,
        "dangling_count": len(dangling),
        "resolved_count": len(resolved_edges),
    }


def load_compat(
    edges: Iterable[Mapping[str, Any]],
    record_ids: Iterable[str],
    aliases: AliasMap | None,
    *,
    apply_map: bool,
) -> dict[str, Any]:
    """Resolve undirected compat endpoints through the same migration map."""
    live = {str(i) for i in record_ids}
    resolved_edges: list[dict[str, str]] = []
    dangling: list[dict[str, str]] = []
    seen_undirected: set[tuple[str, str]] = set()
    for edge in edges:
        raw_a, raw_b = _endpoints(edge)
        a = resolve(raw_a, aliases) if apply_map else raw_a
        b = resolve(raw_b, aliases) if apply_map else raw_b
        pair = tuple(sorted((a, b)))
        row = {
            "a": a,
            "b": b,
            "raw_a": raw_a,
            "raw_b": raw_b,
        }
        missing = [n for n in (a, b) if n not in live]
        if missing:
            dangling.append({**row, "missing": ",".join(missing)})
            continue
        if pair in seen_undirected:
            continue
        seen_undirected.add(pair)
        resolved_edges.append(row)
    return {
        "kind": "compat",
        "apply_map": apply_map,
        "resolved": resolved_edges,
        "dangling": dangling,
        "dangling_count": len(dangling),
        "resolved_count": len(resolved_edges),
        "undirected_count": len(seen_undirected),
    }


def dangling_total(
    provenance_edges: Iterable[Mapping[str, Any]],
    compat_edges: Iterable[Mapping[str, Any]],
    record_ids: Iterable[str],
    aliases: AliasMap | None,
    *,
    apply_map: bool,
) -> dict[str, Any]:
    prov = load_provenance(provenance_edges, record_ids, aliases, apply_map=apply_map)
    compat = load_compat(compat_edges, record_ids, aliases, apply_map=apply_map)
    return {
        "apply_map": apply_map,
        "provenance_dangling": prov["dangling_count"],
        "compat_dangling": compat["dangling_count"],
        "dangling_count": int(prov["dangling_count"]) + int(compat["dangling_count"]),
        "provenance": prov,
        "compat": compat,
    }
