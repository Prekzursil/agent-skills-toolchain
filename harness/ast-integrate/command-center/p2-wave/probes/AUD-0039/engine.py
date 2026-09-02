"""AUD-0039 catalog-edge integrity engine.

Probe 1 uses Kahn (id existence + topological peel).
Probe 2 uses Kosaraju SCCs plus a reverse BFS from terminal-disposition
nodes. Dangling ids are NEVER inserted as graph nodes, so a unit whose only
path would run through a missing id is not counted reachable.

`tools/command-center/catalog.py:_edge_map` drops dangling ids on purpose
before Kahn runs. A dependent of a missing id then looks like a root and
would be counted orderable. Probe 2 exists to catch that hole.
"""
from __future__ import annotations

import json
import re
from collections import deque
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
DEFAULT_TERMINALS = ("DONE-VERIFIED", "DROPPED-BY-OWNER", "SUPERSEDED")
BUCKET_RE = re.compile(r"^B\d{2}$")


def repo_catalog_path() -> Path:
    return REPO / CATALOG_REL


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} root is {type(data).__name__}, expected object")
    return data


def terminal_names(catalog: dict[str, Any]) -> tuple[str, ...]:
    raw = catalog.get("terminal_dispositions")
    if isinstance(raw, list) and raw:
        return tuple(str(x) for x in raw)
    return DEFAULT_TERMINALS


def population(catalog: dict[str, Any], key: str) -> list[dict[str, Any]]:
    raw = catalog.get(key)
    if not isinstance(raw, list):
        return []
    return [row for row in raw if isinstance(row, dict) and str(row.get("id") or "").strip()]


def node_ids(rows: list[dict[str, Any]]) -> list[str]:
    return [str(row["id"]).strip() for row in rows]


def dependencies_of(row: dict[str, Any]) -> list[str]:
    raw = row.get("dependencies")
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for dep in raw:
        token = str(dep).strip()
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def edge_lists(
    rows: list[dict[str, Any]],
) -> tuple[dict[str, list[str]], list[tuple[str, str]]]:
    """Return all declared edges, including dangling targets."""
    adj: dict[str, list[str]] = {}
    pairs: list[tuple[str, str]] = []
    for row in rows:
        nid = str(row["id"]).strip()
        deps = dependencies_of(row)
        adj[nid] = deps
        for dep in deps:
            pairs.append((nid, dep))
    return adj, pairs


def dangling_pairs(
    pairs: list[tuple[str, str]], existing: set[str]
) -> list[tuple[str, str]]:
    return [(src, dst) for src, dst in pairs if dst not in existing]


def existing_adj(
    adj: dict[str, list[str]], existing: set[str]
) -> dict[str, set[str]]:
    """Keep only edges whose target exists. This is Kahn's view — Probe 1."""
    return {
        node: {dep for dep in deps if dep in existing}
        for node, deps in adj.items()
        if node in existing
    }


def kahn_order(existing: set[str], adj_exist: dict[str, set[str]]) -> tuple[list[str], list[str]]:
    remaining = {node: set(adj_exist.get(node, ())) & existing for node in existing}
    order: list[str] = []
    while True:
        ready = sorted(node for node, deps in remaining.items() if not deps)
        if not ready:
            break
        order.extend(ready)
        for node in ready:
            del remaining[node]
        done = set(ready)
        for deps in remaining.values():
            deps -= done
    return order, sorted(remaining)


def kosaraju_sccs(existing: set[str], adj_exist: dict[str, set[str]]) -> list[list[str]]:
    """Iterative Kosaraju. Independent of Kahn; used by Probe 2."""
    nodes = sorted(existing)
    fwd = {n: set(adj_exist.get(n, ())) & existing for n in nodes}
    rev: dict[str, set[str]] = {n: set() for n in nodes}
    for src, dests in fwd.items():
        for dst in dests:
            rev[dst].add(src)

    visited: set[str] = set()
    finish: list[str] = []
    for start in nodes:
        if start in visited:
            continue
        stack: list[tuple[str, Any]] = [(start, iter(sorted(fwd[start])))]
        visited.add(start)
        while stack:
            node, it = stack[-1]
            try:
                nxt = next(it)
            except StopIteration:
                stack.pop()
                finish.append(node)
                continue
            if nxt not in visited:
                visited.add(nxt)
                stack.append((nxt, iter(sorted(fwd[nxt]))))

    assigned: set[str] = set()
    comps: list[list[str]] = []
    for start in reversed(finish):
        if start in assigned:
            continue
        stack2 = [start]
        assigned.add(start)
        comp = [start]
        while stack2:
            node = stack2.pop()
            for nxt in rev[node]:
                if nxt not in assigned:
                    assigned.add(nxt)
                    stack2.append(nxt)
                    comp.append(nxt)
        comps.append(sorted(comp))
    comps.sort(key=lambda c: (len(c), c[0] if c else ""))
    return comps


def cycle_components(sccs: list[list[str]], adj_exist: dict[str, set[str]]) -> list[list[str]]:
    cycles: list[list[str]] = []
    for comp in sccs:
        if len(comp) > 1:
            cycles.append(comp)
            continue
        if len(comp) == 1:
            node = comp[0]
            if node in adj_exist.get(node, ()):
                cycles.append(comp)
    return cycles


def reverse_index(existing: set[str], adj_exist: dict[str, set[str]]) -> dict[str, set[str]]:
    rev: dict[str, set[str]] = {n: set() for n in existing}
    for src, dests in adj_exist.items():
        if src not in existing:
            continue
        for dst in dests:
            if dst in rev:
                rev[dst].add(src)
    return rev


def closure_from(sources: set[str], rev: dict[str, set[str]]) -> set[str]:
    seen: set[str] = set()
    q: deque[str] = deque(sorted(s for s in sources if s in rev))
    while q:
        node = q.popleft()
        if node in seen:
            continue
        seen.add(node)
        for nxt in rev.get(node, ()):
            if nxt not in seen:
                q.append(nxt)
    return seen


def terminals_of(rows: list[dict[str, Any]], names: tuple[str, ...]) -> list[str]:
    out = []
    name_set = set(names)
    for row in rows:
        disp = row.get("disposition")
        if disp in name_set:
            out.append(str(row["id"]).strip())
    return out


def analyze_items(catalog: dict[str, Any]) -> dict[str, Any]:
    names = terminal_names(catalog)
    rows = population(catalog, "items")
    ids = node_ids(rows)
    existing = set(ids)
    adj, pairs = edge_lists(rows)
    dang = dangling_pairs(pairs, existing)
    adj_exist = existing_adj(adj, existing)
    order, residual = kahn_order(existing, adj_exist)
    sccs = kosaraju_sccs(existing, adj_exist)
    cycles = cycle_components(sccs, adj_exist)
    cycle_nodes = sorted({n for comp in cycles for n in comp})
    terms = terminals_of(rows, names)
    rev = reverse_index(existing, adj_exist)
    reachable = sorted(closure_from(set(terms), rev))
    unreachable = sorted(existing - set(reachable))
    naive_roots = sorted(
        node
        for node, deps in adj.items()
        if node in existing and not (set(deps) & existing)
    )
    dangling_only_dependents = sorted(
        {
            src
            for src, dst in dang
            if src in existing and not (set(adj.get(src, [])) & existing)
        }
    )
    return {
        "population": "items",
        "node_count": len(ids),
        "duplicate_ids": sorted({i for i in ids if ids.count(i) > 1}),
        "edge_count": len(pairs),
        "dangling_edge_count": len(dang),
        "dangling_ids": sorted({dst for _, dst in dang}),
        "dangling_edges": [{"from": a, "blocked_by": b} for a, b in dang],
        "kahn_order": order,
        "kahn_residual": residual,
        "acyclic": not cycles,
        "cycle_count": len(cycles),
        "cycle_nodes": cycle_nodes,
        "cycles": cycles,
        "terminal_dispositions": list(names),
        "terminal_count": len(terms),
        "terminal_ids": terms,
        "reachable_from_terminals": reachable,
        "reachable_count": len(reachable),
        "unreachable_from_terminals": unreachable,
        "unreachable_count": len(unreachable),
        "all_existing_ids_named": len(dang) == 0,
        "all_reachable_from_terminals": len(unreachable) == 0,
        "naive_kahn_roots_including_dangling_dependents": naive_roots,
        "dangling_only_dependents": dangling_only_dependents,
    }


def classify_work_unit_edges(catalog: dict[str, Any]) -> dict[str, Any]:
    items = {str(r["id"]).strip() for r in population(catalog, "items")}
    rows = population(catalog, "work_units")
    wu_ids = set(node_ids(rows))
    claimed_buckets = {
        str(r.get("bucket")).strip()
        for r in rows
        if str(r.get("bucket") or "").strip()
    }
    adj, pairs = edge_lists(rows)
    buckets = {
        "resolves_to_work_unit": 0,
        "resolves_to_item": 0,
        "resolves_to_claimed_bucket": 0,
        "unclaimed_bucket_token": 0,
        "unknown_token": 0,
    }
    unknown_tokens: dict[str, int] = {}
    unclaimed_bucket_tokens: dict[str, int] = {}
    for _, dst in pairs:
        if dst in wu_ids:
            buckets["resolves_to_work_unit"] += 1
        elif dst in items:
            buckets["resolves_to_item"] += 1
        elif dst in claimed_buckets:
            buckets["resolves_to_claimed_bucket"] += 1
        elif BUCKET_RE.match(dst):
            buckets["unclaimed_bucket_token"] += 1
            unclaimed_bucket_tokens[dst] = unclaimed_bucket_tokens.get(dst, 0) + 1
        else:
            buckets["unknown_token"] += 1
            unknown_tokens[dst] = unknown_tokens.get(dst, 0) + 1
    adj_exist = existing_adj(adj, wu_ids)
    sccs = kosaraju_sccs(wu_ids, adj_exist)
    cycles = cycle_components(sccs, adj_exist)
    dangling_strict = dangling_pairs(pairs, wu_ids | items)
    return {
        "population": "work_units",
        "node_count": len(wu_ids),
        "edge_count": len(pairs),
        "claimed_buckets": sorted(claimed_buckets),
        "edge_classes": buckets,
        "unknown_tokens": dict(sorted(unknown_tokens.items(), key=lambda kv: (-kv[1], kv[0]))),
        "unclaimed_bucket_tokens": dict(
            sorted(unclaimed_bucket_tokens.items(), key=lambda kv: (-kv[1], kv[0]))
        ),
        "strict_universe": "work_unit id OR items id",
        "strict_dangling_edge_count": len(dangling_strict),
        "cycle_count": len(cycles),
        "cycle_nodes_head": sorted({n for c in cycles for n in c})[:20],
        "acyclic": not cycles,
    }


def analyze_catalog(catalog: dict[str, Any]) -> dict[str, Any]:
    items = analyze_items(catalog)
    work = classify_work_unit_edges(catalog)
    conjunction_ok = (
        items["all_existing_ids_named"]
        and items["acyclic"]
        and items["all_reachable_from_terminals"]
        and work["strict_dangling_edge_count"] == 0
        and work["acyclic"]
    )
    return {
        "items": items,
        "work_units": work,
        "conjunction_holds": conjunction_ok,
    }


def fixture(name: str) -> dict[str, Any]:
    return load_json(HERE / "fixtures" / name)
