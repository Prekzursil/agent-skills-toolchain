"""Support-edge graph: explicit citations only; rank by independent sources.

Probe 1 builds SUPPORT edges from citation fields (not from shared wording).
Probe 2 collapses supporters that share an upstream source_id into one
independent signal. Raw citation count is recorded and must not be used
for ranking.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

SUPPORT_KINDS = frozenset({"SUPPORTS", "SUPPORT", "CITES", "CITATION"})
SKIP_TARGETS = frozenset({"current-documentation", "current-docs", ""})


def _as_citation(raw: Any) -> dict | None:
    if isinstance(raw, str) and raw.strip():
        return {"target_claim_id": raw.strip(), "kind": "SUPPORTS", "span": ""}
    if not isinstance(raw, dict):
        return None
    tgt = (
        raw.get("target_claim_id")
        or raw.get("to")
        or raw.get("target")
        or raw.get("claim_id")
    )
    if not isinstance(tgt, str) or not tgt.strip():
        return None
    kind = str(raw.get("kind") or raw.get("type") or "SUPPORTS").upper()
    if kind in {"CONTRADICTS", "CONTRADICTION", "SUPERSEDES", "SUPERSEDED"}:
        return None
    return {
        "target_claim_id": tgt.strip(),
        "kind": kind if kind in SUPPORT_KINDS else "SUPPORTS",
        "span": str(raw.get("span") or raw.get("quote") or raw.get("kind") or ""),
    }


def normalize_claim(raw: dict, *, origin: str, default_source: str) -> dict | None:
    cid = raw.get("claim_id") or raw.get("id")
    if not isinstance(cid, str) or not cid.strip():
        return None
    source = raw.get("source_id") or raw.get("upstream_document") or default_source
    if isinstance(raw.get("source_lineage"), dict):
        lin = raw["source_lineage"]
        source = (
            lin.get("resolved_url")
            or lin.get("fixture_path")
            or lin.get("source_id")
            or source
        )
    rails = raw.get("rails")
    if (not raw.get("source_id")) and isinstance(rails, list) and rails:
        first = rails[0]
        if isinstance(first, dict):
            source = first.get("permalink") or first.get("final_url") or source
    citations = []
    for item in raw.get("citations") or []:
        cit = _as_citation(item)
        if cit:
            citations.append(cit)
    for item in raw.get("support_edges") or []:
        if not isinstance(item, dict):
            continue
        tgt = item.get("to") or item.get("target") or item.get("target_claim_id")
        if not isinstance(tgt, str):
            continue
        if tgt.strip() in SKIP_TARGETS or tgt.strip().startswith("current-"):
            continue
        cit = _as_citation({"target_claim_id": tgt, "kind": item.get("kind") or "SUPPORTS"})
        if cit:
            citations.append(cit)
    text = str(raw.get("text") or raw.get("statement") or raw.get("claim") or "")
    return {
        "claim_id": cid.strip(),
        "text": text,
        "source_id": str(source),
        "source_path": str(raw.get("source_path") or default_source),
        "origin": str(raw.get("origin") or origin),
        "citations": citations,
    }


def citation_edges(claims: list[dict]) -> tuple[list[dict], list[dict]]:
    """SUPPORT edges from explicit citation fields only."""
    known = {c["claim_id"] for c in claims}
    edges: list[dict] = []
    unresolved: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for claim in claims:
        for cit in claim.get("citations") or []:
            tgt = cit["target_claim_id"]
            key = (claim["claim_id"], tgt)
            if key in seen:
                continue
            seen.add(key)
            row = {
                "from": claim["claim_id"],
                "to": tgt,
                "kind": "SUPPORTS",
                "supporter_source_id": claim["source_id"],
                "citation_span": cit.get("span") or "",
            }
            if tgt not in known:
                unresolved.append({**row, "reason": "dangling-target"})
            else:
                edges.append(row)
    edges.sort(key=lambda e: (e["to"], e["from"]))
    unresolved.sort(key=lambda e: (e["to"], e["from"]))
    return edges, unresolved


def independent_tally(claims: list[dict], edges: list[dict]) -> dict[str, dict]:
    """Collapse supporters that share source_id. Ranking score is independent count."""
    incoming: dict[str, list[dict]] = defaultdict(list)
    for edge in edges:
        incoming[edge["to"]].append(edge)
    out: dict[str, dict] = {}
    for claim in claims:
        cid = claim["claim_id"]
        inc = incoming.get(cid, [])
        sources: list[str] = []
        seen: set[str] = set()
        for edge in inc:
            sid = str(edge["supporter_source_id"])
            if sid not in seen:
                seen.add(sid)
                sources.append(sid)
        raw = len(inc)
        indep = len(sources)
        out[cid] = {
            "claim_id": cid,
            "raw_support_count": raw,
            "independent_source_count": indep,
            "ranking_score": indep,
            "ranking_uses": "independent_source_count",
            "supporting_claim_ids": [e["from"] for e in inc],
            "independent_sources": sources,
            "origin": claim.get("origin"),
            "source_id": claim.get("source_id"),
        }
    return out


def naive_raw_rank(tally: dict[str, dict]) -> dict[str, int]:
    """Detector that ranks by how many agents repeated an idea. Must not be used."""
    return {cid: row["raw_support_count"] for cid, row in tally.items()}


def pair_key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a <= b else (b, a)


def prose_mention_pairs(claims: list[dict]) -> list[tuple[str, str]]:
    """Pairs whose bodies mention each other's ids but have no citation field."""
    ids = [c["claim_id"] for c in claims]
    cited: set[tuple[str, str]] = set()
    for claim in claims:
        for cit in claim.get("citations") or []:
            cited.add(pair_key(claim["claim_id"], cit["target_claim_id"]))
    pairs: list[tuple[str, str]] = []
    for claim in claims:
        text = claim.get("text") or ""
        for other in ids:
            if other == claim["claim_id"]:
                continue
            if other in text:
                key = pair_key(claim["claim_id"], other)
                if key not in cited:
                    pairs.append(key)
    return sorted(set(pairs))


def build(claims: list[dict]) -> dict[str, Any]:
    edges, unresolved = citation_edges(claims)
    tally = independent_tally(claims, edges)
    raw_ne_indep = [
        cid
        for cid, row in tally.items()
        if row["raw_support_count"] != row["independent_source_count"]
    ]
    return {
        "claims": claims,
        "support_edges": edges,
        "unresolved_citations": unresolved,
        "per_claim": [tally[c["claim_id"]] for c in claims],
        "tally": tally,
        "raw_ne_independent": sorted(raw_ne_indep),
        "prose_mention_uncited": prose_mention_pairs(claims),
        "edge_count": len(edges),
        "claim_count": len(claims),
    }
