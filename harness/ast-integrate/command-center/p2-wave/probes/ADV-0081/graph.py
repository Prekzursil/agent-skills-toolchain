#!/usr/bin/env python3
"""ADV-0081 directed support graph: cycle detection and external-root tracing.

Builds claim, document, and external-root nodes from live research claim
records plus planted fixtures. Document-to-origin-claim edges are constructed
from (a) the containing file of each live claim and (b) planted derives_from
edges. Live records do not pre-label those edges; constructing them is Probe 1.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLANTED = HERE / "fixtures" / "planted.json"
LIVE_ROOTS = (REPO / "command-center" / "research",)
REGISTRY = REPO / "command-center" / "CLAIM-REGISTRY.json"

KIND_SUPPORT_CLAIM = "support_claim"
KIND_SUPPORT_DOCUMENT = "support_document"
KIND_DOC_ORIGIN = "document_to_origin_claim"
KIND_EXTERNAL = "external_root"

DEPENDS_KINDS = frozenset(
    {KIND_SUPPORT_CLAIM, KIND_SUPPORT_DOCUMENT, KIND_DOC_ORIGIN, KIND_EXTERNAL}
)


def nid_claim(cid: str) -> str:
    return f"claim:{cid}"


def nid_doc(doc_id: str) -> str:
    return f"doc:{doc_id}"


def nid_ext(url: str) -> str:
    return f"ext:{normalize_url(url)}"


def normalize_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    if parsed.scheme and parsed.netloc:
        path = parsed.path.rstrip("/")
        return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{path}"
    return raw.rstrip("/")


def _walk(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _walk(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk(item)


def _looks_like_claim(row: dict) -> bool:
    if not isinstance(row.get("id"), str) or not row["id"]:
        return False
    if "support_edges" in row or "source_lineage" in row:
        return True
    return "text" in row and "verdict" in row and "id" in row


def harvest_live(repo: Path | None = None) -> dict[str, Any]:
    repo = repo or REPO
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, str]] = []

    def add_node(nid: str, **meta: Any) -> None:
        if nid not in nodes:
            nodes[nid] = {"id": nid, **meta}

    def add_edge(src: str, dst: str, kind: str) -> None:
        rec = {"from": src, "to": dst, "kind": kind}
        if rec not in edges:
            edges.append(rec)

    files: list[Path] = []
    for root in (repo / "command-center" / "research",):
        if root.is_dir():
            files.extend(sorted(root.rglob("*.json")))
    registry = repo / "command-center" / "CLAIM-REGISTRY.json"
    if registry.is_file():
        files.append(registry)

    for path in files:
        rel = path.relative_to(repo).as_posix()
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        doc_nid = nid_doc(rel)
        add_node(doc_nid, kind="document", path=rel, planted=False)
        for row in _walk(doc):
            if not _looks_like_claim(row):
                continue
            cid = row["id"]
            cnid = nid_claim(cid)
            add_node(
                cnid,
                kind="claim",
                claim_id=cid,
                path=rel,
                planted=False,
                text=str(row.get("text") or row.get("claim") or "")[:240],
            )
            add_edge(doc_nid, cnid, KIND_DOC_ORIGIN)
            for other in row.get("support_edges") or []:
                if isinstance(other, str) and other:
                    onid = nid_claim(other)
                    if onid not in nodes:
                        add_node(onid, kind="claim", claim_id=other, path=rel, planted=False)
                    add_edge(cnid, onid, KIND_SUPPORT_CLAIM)
            lineage = row.get("source_lineage")
            url = ""
            if isinstance(lineage, dict):
                url = str(lineage.get("url") or "").strip()
            elif isinstance(lineage, str):
                url = lineage.strip()
            if url:
                enid = nid_ext(url)
                add_node(
                    enid,
                    kind="external",
                    url=normalize_url(url),
                    planted=False,
                    title=(lineage.get("title") if isinstance(lineage, dict) else ""),
                )
                add_edge(cnid, enid, KIND_EXTERNAL)
            for anchor in row.get("evidence_anchors") or []:
                if not isinstance(anchor, str) or not anchor:
                    continue
                if anchor.startswith("http://") or anchor.startswith("https://"):
                    enid = nid_ext(anchor)
                    add_node(enid, kind="external", url=normalize_url(anchor), planted=False)
                    add_edge(cnid, enid, KIND_EXTERNAL)

    return {"nodes": nodes, "edges": edges}


def load_planted(path: Path | None = None) -> dict[str, Any]:
    planted_path = path or PLANTED
    return json.loads(planted_path.read_text(encoding="utf-8"))


def harvest_planted(repo: Path | None = None) -> dict[str, Any]:
    repo = repo or REPO
    spec = load_planted()
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, str]] = []

    def add_node(nid: str, **meta: Any) -> None:
        nodes[nid] = {"id": nid, **meta}

    def add_edge(src: str, dst: str, kind: str) -> None:
        edges.append({"from": src, "to": dst, "kind": kind})

    for claim in spec.get("claims") or []:
        cid = claim["id"]
        cnid = nid_claim(cid)
        add_node(
            cnid,
            kind="claim",
            claim_id=cid,
            planted=True,
            text=str(claim.get("text") or "")[:240],
        )
        lineage = claim.get("source_lineage")
        if isinstance(lineage, dict) and lineage.get("url"):
            url = str(lineage["url"])
            enid = nid_ext(url)
            add_node(
                enid,
                kind="external",
                url=normalize_url(url),
                planted=True,
                title=lineage.get("title") or "",
            )
            add_edge(cnid, enid, KIND_EXTERNAL)

    for document in spec.get("documents") or []:
        did = document["id"]
        dnid = nid_doc(did)
        rel = str(document.get("path") or "")
        add_node(dnid, kind="document", path=rel, planted=True, doc_id=did)
        for origin in document.get("derives_from_claims") or []:
            add_edge(dnid, nid_claim(origin), KIND_DOC_ORIGIN)
        ext = str(document.get("external_root") or "").strip()
        if ext:
            enid = nid_ext(ext)
            add_node(enid, kind="external", url=normalize_url(ext), planted=True)
            add_edge(dnid, enid, KIND_EXTERNAL)

    for edge in spec.get("support_edges") or []:
        src = edge["from"]
        dst = edge["to"]
        kind = edge["kind"]
        src_n = nid_claim(src) if kind.startswith("support") else nid_doc(src)
        if kind == KIND_SUPPORT_CLAIM:
            dst_n = nid_claim(dst)
        elif kind == KIND_SUPPORT_DOCUMENT:
            dst_n = nid_doc(dst)
            src_n = nid_claim(src)
        else:
            dst_n = dst
        add_edge(src_n, dst_n, kind)

    return {"nodes": nodes, "edges": edges, "expected": spec.get("expected") or {}}


def merge_graphs(*graphs: dict[str, Any]) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for graph in graphs:
        for nid, meta in (graph.get("nodes") or {}).items():
            if nid not in nodes:
                nodes[nid] = dict(meta)
            else:
                if meta.get("planted"):
                    nodes[nid]["planted"] = True
        for edge in graph.get("edges") or []:
            key = (edge["from"], edge["to"], edge["kind"])
            if key in seen:
                continue
            seen.add(key)
            edges.append(dict(edge))
    return {"nodes": nodes, "edges": edges}


def adjacency(edges: list[dict[str, str]], kinds: frozenset[str] | None = None) -> dict[str, list[str]]:
    adj: dict[str, list[str]] = defaultdict(list)
    allow = kinds or DEPENDS_KINDS
    for edge in edges:
        if edge["kind"] not in allow:
            continue
        if edge["to"] not in adj[edge["from"]]:
            adj[edge["from"]].append(edge["to"])
    return adj


def tarjan_sccs(nodes: list[str], adj: dict[str, list[str]]) -> list[list[str]]:
    index = 0
    stack: list[str] = []
    onstack: set[str] = set()
    indices: dict[str, int] = {}
    low: dict[str, int] = {}
    sccs: list[list[str]] = []

    def strongconnect(v: str) -> None:
        nonlocal index
        indices[v] = index
        low[v] = index
        index += 1
        stack.append(v)
        onstack.add(v)
        for w in adj.get(v, []):
            if w not in indices:
                strongconnect(w)
                low[v] = min(low[v], low[w])
            elif w in onstack:
                low[v] = min(low[v], indices[w])
        if low[v] == indices[v]:
            scc: list[str] = []
            while True:
                w = stack.pop()
                onstack.remove(w)
                scc.append(w)
                if w == v:
                    break
            sccs.append(scc)

    for node in nodes:
        if node not in indices:
            strongconnect(node)
    return sccs


def cyclic_sccs(sccs: list[list[str]], adj: dict[str, list[str]]) -> list[list[str]]:
    out: list[list[str]] = []
    for scc in sccs:
        if len(scc) > 1:
            out.append(sorted(scc))
            continue
        node = scc[0]
        if node in adj.get(node, []):
            out.append([node])
    return out


def simple_cycles_in_scc(scc: list[str], adj: dict[str, list[str]]) -> list[list[str]]:
    allowed = set(scc)
    cycles: list[list[str]] = []
    seen_norm: set[tuple[str, ...]] = set()

    def normalize(cycle: list[str]) -> tuple[str, ...]:
        body = cycle[:-1]
        start = body.index(min(body))
        return tuple(body[start:] + body[:start])

    def dfs(start: str, node: str, path: list[str]) -> None:
        for nxt in adj.get(node, []):
            if nxt not in allowed:
                continue
            if nxt == start and len(path) >= 1:
                cycle = path + [start]
                key = normalize(cycle)
                if key not in seen_norm:
                    seen_norm.add(key)
                    cycles.append(list(key) + [key[0]])
            elif nxt not in path and nxt >= start:
                path.append(nxt)
                dfs(start, nxt, path)
                path.pop()

    for node in sorted(allowed):
        dfs(node, node, [node])
    return cycles


def member_claims(members: list[str], nodes: dict[str, dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for mid in members:
        meta = nodes.get(mid) or {}
        if meta.get("kind") == "claim":
            out.append(str(meta.get("claim_id") or mid.split(":", 1)[-1]))
        elif mid.startswith("claim:"):
            out.append(mid.split(":", 1)[-1])
    return sorted(set(out))


def direct_externals(
    members: list[str],
    adj: dict[str, list[str]],
    nodes: dict[str, dict[str, Any]],
) -> list[str]:
    urls: set[str] = set()
    for mid in members:
        for dst in adj.get(mid, []):
            meta = nodes.get(dst) or {}
            if meta.get("kind") == "external":
                url = str(meta.get("url") or dst.split(":", 1)[-1])
                if url:
                    urls.add(url)
            if dst.startswith("ext:"):
                urls.add(dst.split(":", 1)[-1])
    return sorted(urls)


def outbound_externals(
    members: list[str],
    adj: dict[str, list[str]],
    nodes: dict[str, dict[str, Any]],
) -> list[str]:
    """Externals reachable after leaving the SCC (not via intra-SCC edges)."""
    member_set = set(members)
    urls: set[str] = set()
    seen: set[str] = set()
    stack: list[str] = []
    for mid in members:
        for dst in adj.get(mid, []):
            if dst not in member_set:
                stack.append(dst)
    while stack:
        node = stack.pop()
        if node in seen or node in member_set:
            continue
        seen.add(node)
        meta = nodes.get(node) or {}
        if meta.get("kind") == "external" or node.startswith("ext:"):
            url = str(meta.get("url") or node.split(":", 1)[-1])
            if url:
                urls.add(url)
            continue
        for dst in adj.get(node, []):
            if dst not in seen and dst not in member_set:
                stack.append(dst)
    return sorted(urls)


def classify_scc(
    members: list[str],
    adj: dict[str, list[str]],
    nodes: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    own = direct_externals(members, adj, nodes)
    reachable = outbound_externals(members, adj, nodes)
    if own:
        roots = own
        klass = "REDUNDANCY" if len(own) == 1 else "MIXED"
    elif not reachable:
        roots = []
        klass = "UNSUPPORTED"
    else:
        roots = reachable
        klass = "REDUNDANCY" if len(reachable) == 1 else "MIXED"
    planted = any((nodes.get(m) or {}).get("planted") for m in members)
    return {
        "members": members,
        "member_claims": member_claims(members, nodes),
        "external_roots": roots,
        "direct_external_roots": own,
        "class": klass,
        "planted": planted,
    }


def claims_losing_support(
    classified: list[dict[str, Any]],
    adj: dict[str, list[str]],
    nodes: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Remove depends-on edges internal to UNSUPPORTED SCCs; recount no-root claims."""
    unsupported_members: set[str] = set()
    for row in classified:
        if row["class"] == "UNSUPPORTED":
            unsupported_members.update(row["members"])
    stripped: dict[str, list[str]] = defaultdict(list)
    for src, dests in adj.items():
        for dst in dests:
            if src in unsupported_members and dst in unsupported_members:
                continue
            stripped[src].append(dst)

    def reaches_external(start: str) -> bool:
        seen: set[str] = set()
        stack = [start]
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            meta = nodes.get(node) or {}
            if meta.get("kind") == "external" or node.startswith("ext:"):
                return True
            for dst in stripped.get(node, []):
                stack.append(dst)
        return False

    lost_live: list[str] = []
    lost_planted: list[str] = []
    for nid in sorted(unsupported_members):
        meta = nodes.get(nid) or {}
        if meta.get("kind") != "claim" and not nid.startswith("claim:"):
            continue
        if reaches_external(nid):
            continue
        cid = str(meta.get("claim_id") or nid.split(":", 1)[-1])
        if meta.get("planted"):
            lost_planted.append(cid)
        else:
            lost_live.append(cid)
    return {
        "live": sorted(set(lost_live)),
        "planted": sorted(set(lost_planted)),
        "live_n": len(set(lost_live)),
        "planted_n": len(set(lost_planted)),
    }


def edge_kind_census(edges: list[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for edge in edges:
        counts[edge["kind"]] += 1
    return dict(counts)


def analyze(repo: Path | None = None) -> dict[str, Any]:
    repo = repo or REPO
    live = harvest_live(repo)
    planted = harvest_planted(repo)
    merged = merge_graphs(live, planted)
    nodes = merged["nodes"]
    edges = merged["edges"]
    adj = adjacency(edges)
    all_nodes = sorted(nodes)
    sccs = tarjan_sccs(all_nodes, adj)
    cyclic = cyclic_sccs(sccs, adj)
    classified = [classify_scc(members, adj, nodes) for members in cyclic]
    cycles: list[dict[str, Any]] = []
    for members in cyclic:
        for cycle in simple_cycles_in_scc(members, adj):
            row = classify_scc(sorted(set(cycle[:-1] if cycle else [])), adj, nodes)
            row["cycle"] = cycle
            cycles.append(row)

    live_cycles = [c for c in cycles if not c["planted"]]
    planted_cycles = [c for c in cycles if c["planted"]]
    doc_claim_cycles = [
        c
        for c in cycles
        if any(m.startswith("doc:") for m in c["members"])
        and any(m.startswith("claim:") for m in c["members"])
    ]
    live_doc_claim = [c for c in doc_claim_cycles if not c["planted"]]
    planted_doc_claim = [c for c in doc_claim_cycles if c["planted"]]
    lost = claims_losing_support(classified, adj, nodes)
    census = edge_kind_census(edges)
    expected = planted.get("expected") or load_planted().get("expected") or {}

    def has_member(rows: list[dict[str, Any]], cid: str) -> bool:
        needle = nid_claim(cid) if not cid.startswith("claim:") else cid
        for row in rows:
            if needle in row["members"] or cid in row.get("member_claims", []):
                return True
        return False

    planted_unsupported_found = has_member(
        [c for c in planted_cycles if c["class"] == "UNSUPPORTED"],
        "C-PLANT-UNSUPPORTED",
    )
    planted_chain_cyclic = has_member(cycles, "C-PLANT-CHAIN")
    red_rows = [
        c
        for c in planted_cycles
        if "C-PLANT-RED-A" in c.get("member_claims", [])
        or nid_claim("C-PLANT-RED-A") in c["members"]
    ]
    planted_red_ok = bool(red_rows) and all(r["class"] == "REDUNDANCY" for r in red_rows)

    live_f1f2 = [
        c
        for c in live_cycles
        if "RES-0075-F1" in c.get("member_claims", [])
        and "RES-0075-F2" in c.get("member_claims", [])
    ]
    live_f1f2_redundancy = bool(live_f1f2) and all(c["class"] == "REDUNDANCY" for c in live_f1f2)

    graph_representable = (
        census.get(KIND_SUPPORT_CLAIM, 0) > 0
        and census.get(KIND_DOC_ORIGIN, 0) > 0
        and census.get(KIND_EXTERNAL, 0) > 0
    )

    return {
        "n_nodes": len(nodes),
        "n_edges": len(edges),
        "edge_kind_census": census,
        "n_live_claims": sum(
            1
            for n in nodes.values()
            if n.get("kind") == "claim" and not n.get("planted")
        ),
        "n_cyclic_sccs": len(cyclic),
        "n_simple_cycles": len(cycles),
        "n_live_simple_cycles": len(live_cycles),
        "n_planted_simple_cycles": len(planted_cycles),
        "n_live_document_claim_cycles": len(live_doc_claim),
        "n_planted_document_claim_cycles": len(planted_doc_claim),
        "cycles": cycles,
        "classified_sccs": classified,
        "claims_losing_support": lost,
        "graph_representable": graph_representable,
        "controls": {
            "planted_unsupported_cycle_found": planted_unsupported_found,
            "planted_chain_acyclic": not planted_chain_cyclic,
            "planted_redundancy_classified": planted_red_ok,
            "live_f1_f2_redundancy": live_f1f2_redundancy,
            "gate_fires_on_unsupported": planted_unsupported_found,
            "gate_silent_on_chain": not planted_chain_cyclic,
            "gate_silent_on_redundancy": planted_red_ok,
        },
        "expected": expected,
        "pass": (
            planted_unsupported_found
            and (not planted_chain_cyclic)
            and planted_red_ok
            and graph_representable
        ),
    }


def probe1_payload(repo: Path | None = None) -> dict[str, Any]:
    """Cycle enumeration (Tarjan SCC + simple cycles). Does not classify roots."""
    full = analyze(repo)
    cycles = []
    for row in full["cycles"]:
        cycles.append(
            {
                "cycle": row["cycle"],
                "member_claims": row["member_claims"],
                "members": row["members"],
                "planted": row["planted"],
                "is_document_claim_cycle": any(m.startswith("doc:") for m in row["members"])
                and any(m.startswith("claim:") for m in row["members"]),
            }
        )
    ctrl = full["controls"]
    return {
        "probe": "probe1-cycle-enumeration",
        "unit_id": "ADV-0081",
        "n_nodes": full["n_nodes"],
        "n_edges": full["n_edges"],
        "edge_kind_census": full["edge_kind_census"],
        "n_simple_cycles": full["n_simple_cycles"],
        "n_live_simple_cycles": full["n_live_simple_cycles"],
        "n_live_document_claim_cycles": full["n_live_document_claim_cycles"],
        "n_planted_document_claim_cycles": full["n_planted_document_claim_cycles"],
        "cycles": cycles,
        "graph_representable": full["graph_representable"],
        "controls": {
            "planted_unsupported_cycle_found": ctrl["planted_unsupported_cycle_found"],
            "planted_chain_acyclic": ctrl["planted_chain_acyclic"],
        },
        "pass": full["pass"] and ctrl["planted_unsupported_cycle_found"] and ctrl["planted_chain_acyclic"],
        "computed_not_asserted": True,
    }


def probe2_payload(repo: Path | None = None) -> dict[str, Any]:
    """External-root tracing from SCCs. Rebuilds the graph; does not read probe 1 output."""
    full = analyze(repo)
    classified = []
    for row in full["classified_sccs"]:
        classified.append(
            {
                "members": row["members"],
                "member_claims": row["member_claims"],
                "class": row["class"],
                "external_roots": row["external_roots"],
                "planted": row["planted"],
            }
        )
    ctrl = full["controls"]
    lost = full["claims_losing_support"]
    return {
        "probe": "probe2-external-root-trace",
        "unit_id": "ADV-0081",
        "classified_sccs": classified,
        "n_unsupported": sum(1 for r in classified if r["class"] == "UNSUPPORTED"),
        "n_redundancy": sum(1 for r in classified if r["class"] == "REDUNDANCY"),
        "n_mixed": sum(1 for r in classified if r["class"] == "MIXED"),
        "claims_losing_support": lost,
        "controls": {
            "planted_unsupported_reclassified": ctrl["planted_unsupported_cycle_found"],
            "planted_redundancy_classified": ctrl["planted_redundancy_classified"],
            "gate_fires_on_unsupported": ctrl["gate_fires_on_unsupported"],
            "gate_silent_on_chain": ctrl["gate_silent_on_chain"],
            "gate_silent_on_redundancy": ctrl["gate_silent_on_redundancy"],
            "live_f1_f2_redundancy": ctrl["live_f1_f2_redundancy"],
        },
        "pass": (
            ctrl["planted_unsupported_cycle_found"]
            and ctrl["planted_redundancy_classified"]
            and ctrl["gate_silent_on_chain"]
            and ctrl["gate_silent_on_redundancy"]
        ),
        "computed_not_asserted": True,
        "rederived_from": "live research JSON + fixtures/planted.json, not ADV-0081 report",
    }
