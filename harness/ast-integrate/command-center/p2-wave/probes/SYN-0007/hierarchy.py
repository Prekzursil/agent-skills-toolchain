"""Load SYN-0001 hierarchy when present; otherwise reconstruct a typed DAG
from catalog CC-* and SYN-* dependency edges.

Reconstruction is honest about provenance: it is not a substitute SYN-0001
artifact, it is the best on-disk causal structure this unit can rank today.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from rank import PHASE_ORDER, RankError, max_depth, phase_index

SPEC_RE = re.compile(r"_USER-PROMPTS\.md:(\d+(?:-\d+)?)")
UID_RE = re.compile(r"^(CC|SYN)-\d{4}$")

SYN0001 = "command-center/synthesis/SYN-0001.root-cause-hierarchy.json"
SYN0004 = "command-center/receipts/SYN-0004.json"
PHASE_GRAPH = "command-center/PHASE-GRAPH.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def spec_line_of(unit: dict[str, Any]) -> str:
    blobs = [str(unit.get("question_or_target") or "")]
    for item in unit.get("inputs") or []:
        blobs.append(str(item))
    text = "\n".join(blobs)
    m = SPEC_RE.search(text)
    if m:
        return f"_USER-PROMPTS.md:{m.group(1)}"
    uid = str(unit.get("id") or "")
    src = str(unit.get("_source_slice_file") or "WORK-UNIT-CATALOG.json")
    return f"{src}#{uid}"


def severity_of_unit(unit: dict[str, Any]) -> str:
    if unit.get("owner_approval_required") is True:
        return "P0"
    try:
        timeout = int(unit.get("timeout_seconds") or 0)
    except (TypeError, ValueError):
        timeout = 0
    if timeout >= 7200:
        return "P1"
    if timeout >= 3600:
        return "P2"
    return "P3"


def _parse_live_hierarchy(doc: Any) -> dict[str, Any] | None:
    if not isinstance(doc, dict):
        return None
    nodes = doc.get("nodes")
    edges = doc.get("edges")
    if isinstance(doc.get("hierarchy"), dict):
        h = doc["hierarchy"]
        nodes = h.get("nodes", nodes)
        edges = h.get("edges", edges)
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return None
    out_nodes: list[dict[str, Any]] = []
    for n in nodes:
        if not isinstance(n, dict) or not n.get("id"):
            continue
        ntype = str(n.get("type") or n.get("kind") or "").upper()
        if ntype not in {"CAUSE", "MECHANISM", "SYMPTOM"}:
            continue
        claims = n.get("claim_ids") or n.get("claims") or [str(n["id"])]
        if not isinstance(claims, list):
            claims = [str(n["id"])]
        phase = str(n.get("phase") or n.get("available_at_phase") or "14")
        sev = str(n.get("severity") or "P2").upper()
        out_nodes.append(
            {
                "id": str(n["id"]),
                "type": ntype,
                "phase": phase,
                "claim_ids": [str(c) for c in claims if str(c).strip()],
                "severity": sev if sev in {"P0", "P1", "P2", "P3"} else "P2",
                "title": str(n.get("title") or n.get("label") or n["id"]),
                "spec_line": str(n.get("spec_line") or f"{SYN0001}#{n['id']}"),
            }
        )
    out_edges: list[dict[str, Any]] = []
    for e in edges:
        if not isinstance(e, dict):
            continue
        p = str(e.get("parent") or e.get("from") or e.get("source") or "")
        c = str(e.get("child") or e.get("to") or e.get("target") or "")
        if p and c:
            out_edges.append(
                {
                    "parent": p,
                    "child": c,
                    "mechanism": str(e.get("mechanism") or e.get("via") or "catalog-edge"),
                }
            )
    if len(out_nodes) < 4 or len(out_edges) < 3:
        return None
    return {
        "source": SYN0001,
        "nodes": out_nodes,
        "edges": out_edges,
        "costs": doc.get("costs") if isinstance(doc.get("costs"), dict) else {},
    }


def _apply_syn0004(hierarchy: dict[str, Any], rec: Any) -> None:
    if not isinstance(rec, dict):
        return
    rows = rec.get("rows") or rec.get("causes") or rec.get("reconciliation") or []
    if not isinstance(rows, list):
        return
    by_id = {n["id"]: n for n in hierarchy["nodes"]}
    for row in rows:
        if not isinstance(row, dict):
            continue
        cid = str(row.get("cause_id") or row.get("id") or "")
        sev = str(row.get("severity") or row.get("computed_severity") or "").upper()
        if cid in by_id and sev in {"P0", "P1", "P2", "P3"}:
            by_id[cid]["severity"] = sev
            by_id[cid]["severity_source"] = SYN0004


def reconstruct_from_catalog(catalog: dict[str, Any]) -> dict[str, Any]:
    units = [
        u
        for u in (catalog.get("work_units") or [])
        if isinstance(u, dict) and UID_RE.match(str(u.get("id") or ""))
    ]
    by_id = {str(u["id"]): u for u in units}
    kids: dict[str, list[str]] = defaultdict(list)
    parents: dict[str, list[str]] = defaultdict(list)
    edges: list[dict[str, Any]] = []
    seen_e: set[tuple[str, str]] = set()
    for u in units:
        uid = str(u["id"])
        for dep in u.get("dependencies") or []:
            d = str(dep)
            if d not in by_id or d == uid:
                continue
            key = (d, uid)
            if key in seen_e:
                continue
            seen_e.add(key)
            kids[d].append(uid)
            parents[uid].append(d)
            classes = u.get("failure_classification") or []
            mech = str(classes[0]) if classes else "dependency"
            edges.append({"parent": d, "child": uid, "mechanism": mech})

    nodes: list[dict[str, Any]] = []
    costs: dict[str, Any] = {}
    for u in units:
        uid = str(u["id"])
        n_in = len(parents.get(uid) or [])
        n_out = len(kids.get(uid) or [])
        if n_in == 0:
            ntype = "CAUSE"
        elif n_out == 0:
            ntype = "SYMPTOM"
        else:
            ntype = "MECHANISM"
        try:
            timeout = int(u.get("timeout_seconds") or 0)
        except (TypeError, ValueError):
            timeout = 0
        if timeout <= 0:
            timeout = 1800
        phase = str(u.get("phase") or "14")
        try:
            phase_index(phase)
        except RankError:
            phase = "14"
        nodes.append(
            {
                "id": uid,
                "type": ntype,
                "phase": phase,
                "claim_ids": [uid],
                "severity": severity_of_unit(u),
                "title": str(u.get("title") or uid),
                "spec_line": spec_line_of(u),
            }
        )
        costs[uid] = {"basis": "DERIVED", "seconds": timeout}

    depth = max_depth(nodes, edges)
    if depth < 2:
        raise RankError("empty-subtree", f"reconstructed max_depth={depth} < 2")
    return {
        "source": f"{CATALOG}#work_units[CC|SYN] (SYN-0001 artifact absent)",
        "nodes": nodes,
        "edges": edges,
        "costs": costs,
        "max_depth": depth,
        "acyclic": True,
    }


def load_hierarchy(repo: Path) -> dict[str, Any]:
    catalog = _load_json(repo / CATALOG)
    live_path = repo / SYN0001
    hierarchy: dict[str, Any] | None = None
    source_note = "reconstructed"
    if live_path.is_file() and live_path.stat().st_size > 0:
        try:
            hierarchy = _parse_live_hierarchy(_load_json(live_path))
        except (OSError, json.JSONDecodeError):
            hierarchy = None
        if hierarchy is not None:
            source_note = "live-SYN-0001"
            if not hierarchy.get("costs"):
                recon = reconstruct_from_catalog(catalog)
                for nid, cost in recon["costs"].items():
                    hierarchy["costs"].setdefault(nid, cost)
    if hierarchy is None:
        hierarchy = reconstruct_from_catalog(catalog)
        source_note = "reconstructed-catalog-CC-SYN"

    syn4 = repo / SYN0004
    syn4_present = syn4.is_file() and syn4.stat().st_size > 0
    if syn4_present:
        try:
            _apply_syn0004(hierarchy, _load_json(syn4))
        except (OSError, json.JSONDecodeError):
            syn4_present = False

    pg = repo / PHASE_GRAPH
    pg_present = pg.is_file() and pg.stat().st_size > 0
    hierarchy["phase_order"] = list(PHASE_ORDER)
    hierarchy["inputs_used"] = [
        {
            "path": SYN0001,
            "role": "root-cause-hierarchy",
            "present": live_path.is_file() and live_path.stat().st_size > 0,
        },
        {
            "path": SYN0004,
            "role": "severity-reconciliation",
            "present": syn4_present,
        },
        {
            "path": PHASE_GRAPH,
            "role": "phase-availability",
            "present": pg_present,
        },
        {
            "path": CATALOG,
            "role": "reconstruction-source" if source_note.startswith("reconstructed") else "cost-timeouts",
            "present": True,
        },
    ]
    hierarchy["source_note"] = source_note
    if "max_depth" not in hierarchy:
        hierarchy["max_depth"] = max_depth(hierarchy["nodes"], hierarchy["edges"])
    return hierarchy
