"""Load claim records for AUD-0071.

Prefers AUD-0068 canonical claims and AUD-0074 lineage when those artifacts
exist. Always includes the planted five-from-one control. On-tree research
records contribute only explicit support_edges, never prose co-occurrence.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from graph import normalize_claim

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CONTROL = HERE / "fixtures" / "control_claims.json"
AUD0068 = REPO / "command-center" / "audit" / "AUD-0068-claim-extraction-canonical.json"
AUD0074 = REPO / "command-center" / "audit" / "AUD-0074-source-lineage-graph.json"
RESEARCH = REPO / "command-center" / "research"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _claim_lists(doc: Any) -> list[dict]:
    if isinstance(doc, list):
        return [x for x in doc if isinstance(x, dict)]
    if not isinstance(doc, dict):
        return []
    for key in ("claims", "records", "claim_records", "items", "nodes"):
        val = doc.get(key)
        if isinstance(val, list):
            return [x for x in val if isinstance(x, dict)]
    report = doc.get("report")
    if isinstance(report, dict):
        return _claim_lists(report)
    return []


def load_control() -> list[dict]:
    doc = _load_json(CONTROL)
    out = []
    for row in doc.get("claims") or []:
        n = normalize_claim(
            row,
            origin="control",
            default_source="command-center/p2-wave/probes/AUD-0071/fixtures/control_claims.json",
        )
        if n:
            out.append(n)
    return out


def load_aud0068() -> tuple[list[dict], dict]:
    meta = {
        "path": "command-center/audit/AUD-0068-claim-extraction-canonical.json",
        "present": AUD0068.is_file(),
        "bytes": AUD0068.stat().st_size if AUD0068.is_file() else 0,
        "state": None,
        "claim_count": 0,
    }
    if not AUD0068.is_file():
        return [], meta
    doc = _load_json(AUD0068)
    if isinstance(doc, dict):
        meta["state"] = doc.get("state")
    claims = []
    for row in _claim_lists(doc):
        n = normalize_claim(row, origin="aud-0068", default_source=str(AUD0068))
        if n:
            claims.append(n)
    meta["claim_count"] = len(claims)
    return claims, meta


def _lineage_map() -> tuple[dict[str, str], dict]:
    meta = {
        "path": "command-center/audit/AUD-0074-source-lineage-graph.json",
        "present": AUD0074.is_file(),
        "bytes": AUD0074.stat().st_size if AUD0074.is_file() else 0,
        "state": None,
        "overlay_count": 0,
    }
    mapping: dict[str, str] = {}
    if not AUD0074.is_file():
        return mapping, meta
    doc = _load_json(AUD0074)
    if isinstance(doc, dict):
        meta["state"] = doc.get("state")
        nodes = doc.get("nodes") or doc.get("artifacts") or []
        if isinstance(nodes, list):
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                nid = node.get("id") or node.get("path") or node.get("artifact")
                up = node.get("upstream") or node.get("source_id") or node.get("derives_from")
                if isinstance(nid, str) and isinstance(up, str) and nid and up:
                    mapping[nid] = up
        edges = doc.get("edges") or doc.get("lineage_edges") or []
        if isinstance(edges, list):
            for edge in edges:
                if not isinstance(edge, dict):
                    continue
                frm = edge.get("from") or edge.get("child") or edge.get("downstream")
                to = edge.get("to") or edge.get("parent") or edge.get("upstream")
                if isinstance(frm, str) and isinstance(to, str) and frm and to:
                    mapping.setdefault(frm, to)
    meta["overlay_count"] = len(mapping)
    return mapping, meta


def load_research() -> list[dict]:
    if not RESEARCH.is_dir():
        return []
    claims = []
    for path in sorted(RESEARCH.rglob("*.json")):
        try:
            doc = _load_json(path)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        rel = path.relative_to(REPO).as_posix()
        for row in _claim_lists(doc):
            n = normalize_claim(row, origin="on-tree-research", default_source=rel)
            if n:
                claims.append(n)
    return claims


def merge_claims(*groups: list[dict]) -> list[dict]:
    """Control ids win. Later groups fill new ids only."""
    by_id: dict[str, dict] = {}
    order: list[str] = []
    for group in groups:
        for claim in group:
            cid = claim["claim_id"]
            if cid in by_id:
                continue
            by_id[cid] = claim
            order.append(cid)
    return [by_id[i] for i in order]


def apply_lineage(claims: list[dict], mapping: dict[str, str]) -> list[dict]:
    if not mapping:
        return claims
    out = []
    for claim in claims:
        row = dict(claim)
        path = row.get("source_path") or ""
        if path in mapping:
            row["source_id"] = mapping[path]
            row["lineage_overlay"] = True
        elif row["claim_id"] in mapping:
            row["source_id"] = mapping[row["claim_id"]]
            row["lineage_overlay"] = True
        out.append(row)
    return out


def load_corpus() -> dict[str, Any]:
    control = load_control()
    aud_claims, aud_meta = load_aud0068()
    lineage, lin_meta = _lineage_map()
    research = load_research()
    merged = merge_claims(control, aud_claims, research)
    merged = apply_lineage(merged, lineage)
    return {
        "claims": merged,
        "control_count": len(control),
        "aud0068": aud_meta,
        "aud0074": lin_meta,
        "research_count": len(research),
        "loaded_count": len(merged),
    }
