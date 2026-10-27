#!/usr/bin/env python3
"""AUD-0071 probe 1 - rebuild support edges from explicit citation data.

Re-derives the per-claim support accounting straight from the delivered
graph's raw parts (nodes' source_id + support_edges) - a mechanically
different detector from the builder that parsed the corpus text: every edge
must resolve to real endpoints, carry a citation span naming its target,
match node citation_count, and reproduce every per_claim row exactly.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ART = REPO / "command-center" / "audit" / "AUD-0071-support-edge-graph.json"
UNIT = "AUD-0071"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("sentinel") or "") and str(doc.get("sentinel")) not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if doc.get("unit_id") != UNIT and doc.get("id") != UNIT:
        return fail(f"unit_id {doc.get('unit_id')}")

    nodes = doc.get("nodes") or []
    edges = doc.get("support_edges") or []
    per_claim = doc.get("per_claim") or []
    if not nodes or not per_claim:
        return fail("graph empty (nodes/per_claim)")
    by_id = {n["id"]: n for n in nodes}
    if len(by_id) != len(nodes):
        return fail("duplicate node ids")
    hl = doc.get("headline") or {}
    if hl.get("claim_count") not in (None, len(nodes)):
        return fail(f"headline claim_count={hl.get('claim_count')} graph={len(nodes)}")
    if hl.get("support_edge_count") not in (None, len(edges)):
        return fail(f"headline support_edge_count={hl.get('support_edge_count')} graph={len(edges)}")

    inbound: dict[str, list[dict]] = {}
    for e in edges:
        src, dst = e.get("from"), e.get("to")
        if src not in by_id:
            return fail(f"edge from-node missing: {src}")
        if dst not in by_id:
            return fail(f"edge to-node missing: {dst}")
        if str(e.get("kind") or "").upper() != "SUPPORTS":
            return fail(f"edge kind not SUPPORTS: {e}")
        if e.get("supporter_source_id") != by_id[src].get("source_id"):
            return fail(
                f"edge supporter_source_id {e.get('supporter_source_id')} != "
                f"from-node source_id {by_id[src].get('source_id')} ({src}->{dst})"
            )
        span = str(e.get("citation_span") or "")
        if f"cites {dst}" not in span:
            return fail(f"citation_span does not cite target: {span} -> {dst}")
        inbound.setdefault(dst, []).append(e)

    # citation_count is the node's OWN (outgoing) citation record count, not
    # inbound support: a claim that makes no citations has 0 regardless of
    # how many claims cite it. A node may cite a target absent from the
    # graph (dangling citation): citation_count then exceeds outdegree, and
    # the total excess must equal headline.unresolved_citation_count.
    outdeg: dict[str, int] = {}
    for e in edges:
        outdeg[e["from"]] = outdeg.get(e["from"], 0) + 1
    dangling = []
    for n in nodes:
        have = int(n.get("citation_count") or 0)
        out = outdeg.get(n["id"], 0)
        if have < out:
            return fail(f"node {n['id']} citation_count={have} < outgoing edges={out}")
        if have > out:
            dangling.append(f"{n['id']}:{have - out}")
    want_unresolved = (doc.get("headline") or {}).get("unresolved_citation_count")
    if want_unresolved not in (None, len(dangling)):
        return fail(
            f"unresolved citations: headline={want_unresolved} excess={dangling}"
        )
    if dangling:
        print(f"declared dangling citers (citation_count > resolved edges): {dangling}")

    rebuilt = {}
    for n in nodes:
        cid = n["id"]
        ins = inbound.get(cid, [])
        sources = sorted({e["supporter_source_id"] for e in ins})
        rebuilt[cid] = {
            "claim_id": cid,
            "independent_source_count": len(sources),
            "independent_sources": sources,
            "raw_support_count": len(ins),
            "source_id": n.get("source_id"),
            "supporting_claim_ids": sorted(e["from"] for e in ins),
        }
    mismatches = []
    for row in per_claim:
        cid = row.get("claim_id")
        if cid not in rebuilt:
            mismatches.append(f"{cid}: not in graph")
            continue
        for key in ("independent_source_count", "independent_sources",
                    "raw_support_count", "source_id", "supporting_claim_ids"):
            if row.get(key) != rebuilt[cid][key]:
                mismatches.append(f"{cid}.{key}: artifact={row.get(key)} rebuilt={rebuilt[cid][key]}")
    if len(per_claim) != len(rebuilt):
        mismatches.append(f"per_claim rows={len(per_claim)} rebuilt={len(rebuilt)}")
    if mismatches:
        for m in mismatches[:10]:
            print(f"  MISMATCH {m}")
        return fail(f"per_claim re-derivation mismatched on {len(mismatches)} field(s)")

    print(f"rebuilt nodes={len(nodes)} edges={len(edges)} per_claim rows exact")
    print(f"SUCCESS:{UNIT}-probe1 citation support edges rebuilt from raw graph")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
