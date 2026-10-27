"""Citation graph + circular-citation detector (IMP-0314)."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

CITE_KINDS = ("CITES", "SUPPORTS", "ATTACKS", "REBUTS", "GROUNDS")


def _graph(doc: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    ag = doc.get("argument_graph") or {}
    return list(ag.get("nodes") or []), list(ag.get("edges") or [])


def _cycles(nodes: list[dict], edges: list[dict]) -> list[list[str]]:
    adj: dict[str, list[str]] = defaultdict(list)
    for e in edges:
        src, dst = str(e.get("src") or ""), str(e.get("dst") or "")
        if src and dst:
            adj[src].append(dst)
    ids = [str(n.get("id") or "") for n in nodes if n.get("id")]
    found: list[list[str]] = []
    seen_sig: set[tuple[str, ...]] = set()

    def dfs(node: str, stack: list[str], in_stack: set[str]) -> None:
        stack.append(node)
        in_stack.add(node)
        for nxt in adj.get(node, []):
            if nxt in in_stack:
                i = stack.index(nxt)
                cyc = stack[i:] + [nxt]
                sig = tuple(sorted(set(cyc[:-1])))
                if sig and sig not in seen_sig:
                    seen_sig.add(sig)
                    found.append(cyc)
            elif nxt not in stack:
                dfs(nxt, stack, in_stack)
        stack.pop()
        in_stack.discard(node)

    for nid in ids:
        dfs(nid, [], set())
    return found


def analyse(doc: dict[str, Any], repo: Path | None = None) -> dict[str, Any]:
    nodes, edges = _graph(doc)
    if not nodes and not edges:
        return {
            "status": "NOT-CHECKED",
            "fired": False,
            "cycles": [],
            "distinct_url_count": 0,
            "circular_citation": {"status": "NOT-CHECKED"},
        }
    raw = _cycles(nodes, edges)
    cycles = []
    for path in raw:
        cycles.append(
            {
                "path": path,
                "path_str": "->".join(path),
            }
        )
    urls = {
        str(n.get("url"))
        for n in nodes
        if isinstance(n.get("url"), str) and n.get("url")
    }
    fired = bool(cycles)
    status = "FIRE" if fired else "SILENT"
    return {
        "status": status,
        "fired": fired,
        "cycles": cycles,
        "distinct_url_count": len(urls),
        "circular_citation": {"status": status},
        "fixture_id": doc.get("fixture_id"),
    }


def status_line(report: dict[str, Any]) -> str:
    return (
        f"fixture={report.get('fixture_id')} status={report.get('status')} "
        f"fired={report.get('fired')} cycles={len(report.get('cycles') or [])}"
    )


def url_cardinality_hides_cycle(report: dict[str, Any]) -> bool:
    return bool(report.get("fired")) and int(report.get("distinct_url_count") or 0) < 2


def naive_document_cycle_fires(doc: dict[str, Any]) -> bool:
    """Mutant: any mutual mention of documents is a cycle, even distinct facts."""
    refs = doc.get("document_cross_refs") or {}
    if isinstance(refs, dict):
        for a, dests in refs.items():
            for b in dests or []:
                if a in (refs.get(b) or []):
                    return True
    nodes, _edges = _graph(doc)
    origins = {str(n.get("origin_id") or "") for n in nodes if n.get("origin_id")}
    return len(origins) >= 2
