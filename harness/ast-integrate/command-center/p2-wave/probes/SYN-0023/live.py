#!/usr/bin/env python3
"""Load live SYN-0010 / SYN-0008 / CLAIM-REGISTRY inputs if present."""
from __future__ import annotations

import json
from typing import Any

from attribute import REPO, artifact_identity, attribute_scenario

LIVE_PATHS = {
    "SYN-0010": "command-center/receipts/SYN-0010.json",
    "SYN-0008": "command-center/synthesis/SYN-0008.candidate-syntheses.json",
    "CLAIM-REGISTRY": "command-center/CLAIM-REGISTRY.json",
    "SYN-0012": "command-center/synthesis/SYN-0012.sensitivity.json",
}


def _positive(val: Any) -> bool:
    if val is True:
        return True
    return val in (1, "1", "true", "TRUE", "AGREED", "agreed", "yes")


def inventory_row(role: str, rel: str) -> tuple[dict, Any]:
    path = REPO / rel
    row = {"role": role, "path": rel, "present": False, "parse": "ABSENT", "bytes": 0}
    if not path.is_file() or path.stat().st_size <= 0:
        return row, None
    row["present"] = True
    row["bytes"] = path.stat().st_size
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        row["parse"] = type(exc).__name__
        return row, None
    row["parse"] = "OK"
    return row, doc


def load_inventory() -> tuple[list[dict], dict[str, Any]]:
    rows = []
    docs: dict[str, Any] = {}
    for role, rel in LIVE_PATHS.items():
        row, doc = inventory_row(role, rel)
        rows.append(row)
        docs[role] = doc
    return rows, docs


def as_artifact(obj: Any) -> dict | None:
    if isinstance(obj, str) and obj.strip():
        text = obj.replace("\\", "/").strip()
        if "/" in text or "." in text:
            return {"path": text, "artifact_id": text, "parents": []}
        return {"artifact_id": text, "parents": []}
    if not isinstance(obj, dict):
        return None
    rec = dict(obj)
    rec.setdefault("parents", rec.get("derived_from") or rec.get("parent") or [])
    if isinstance(rec["parents"], str):
        rec["parents"] = [rec["parents"]]
    if not rec.get("artifact_id"):
        rec["artifact_id"] = rec.get("id") or rec.get("path") or rec.get("sha256")
    if rec.get("artifact_id") or rec.get("sha256") or rec.get("path"):
        rec["artifact_id"] = str(
            rec.get("artifact_id") or rec.get("sha256") or rec.get("path")
        )
        return rec
    return None


def normalize_conclusion(item: Any) -> dict | None:
    if isinstance(item, str) and item.strip():
        return {"conclusion_id": item.strip(), "text": item.strip(), "agents": None}
    if not isinstance(item, dict):
        return None
    cid = (
        item.get("conclusion_id")
        or item.get("item_id")
        or item.get("id")
        or item.get("canonical_mechanism")
        or item.get("mechanism_id")
    )
    if cid is None:
        return None
    text = (
        item.get("text")
        or item.get("conclusion")
        or item.get("statement")
        or item.get("claim")
        or str(cid)
    )
    agents = item.get("agents") or item.get("synthesizers") or item.get("raters")
    if isinstance(agents, dict):
        agents = [str(k) for k, v in agents.items() if _positive(v)]
    elif isinstance(agents, list):
        agents = [str(a) for a in agents]
    else:
        agents = None
    return {"conclusion_id": str(cid), "text": str(text), "agents": agents}


def extract_agreed(doc: Any) -> list[dict]:
    if not isinstance(doc, dict):
        return []
    for key in ("agreed_conclusions", "agreed_set", "agreed_items", "agreed"):
        val = doc.get(key)
        if isinstance(val, list) and val:
            out = [row for row in (normalize_conclusion(x) for x in val) if row]
            if out:
                return out
    for key in ("per_item", "items", "conclusions", "matrix_rows", "universe"):
        val = doc.get(key)
        if not isinstance(val, list):
            continue
        out = []
        for item in val:
            if not isinstance(item, dict):
                continue
            flag = item.get("agreed")
            if flag is True or str(flag).upper() in {"AGREED", "TRUE", "YES"}:
                row = normalize_conclusion(item)
                if row:
                    out.append(row)
                continue
            agents = item.get("agents")
            if isinstance(agents, dict):
                vals = list(agents.values())
                if len(vals) >= 2 and all(_positive(v) for v in vals):
                    row = normalize_conclusion(item)
                    if row:
                        out.append(row)
        if out:
            return out
    return []


def extract_coefficient(doc: Any) -> dict:
    if not isinstance(doc, dict):
        return {
            "present": False,
            "value": None,
            "null_model": None,
            "universe_size": None,
        }
    coef = doc.get("coefficient") or doc.get("agreement_coefficient") or doc.get("kappa")
    return {
        "present": coef is not None,
        "value": coef,
        "null_model": doc.get("null_model") or doc.get("null"),
        "universe_size": doc.get("universe_size") or doc.get("item_universe_size"),
    }


def extract_candidates(doc: Any) -> list[dict]:
    if not isinstance(doc, dict):
        return []
    raw = (
        doc.get("candidates")
        or doc.get("syntheses")
        or doc.get("synthesizers")
        or doc.get("candidate_syntheses")
        or []
    )
    if not isinstance(raw, list):
        return []
    out = []
    for cand in raw:
        if not isinstance(cand, dict):
            continue
        agent = (
            cand.get("synthesizer_id")
            or cand.get("agent_id")
            or cand.get("id")
            or cand.get("vendor_model")
        )
        parts = (
            cand.get("partition_manifest")
            or cand.get("partition")
            or cand.get("inputs")
            or cand.get("admitted_inputs")
            or []
        )
        arts = []
        if isinstance(parts, list):
            for item in parts:
                art = as_artifact(item)
                if art:
                    arts.append(art)
        conclusions = (
            cand.get("conclusions") or cand.get("findings") or cand.get("root_causes") or []
        )
        out.append(
            {
                "agent_id": str(agent) if agent is not None else "unknown",
                "artifacts": arts,
                "conclusions": conclusions if isinstance(conclusions, list) else [],
            }
        )
    return out


def extract_lineage_edges(doc: Any) -> list[tuple[str, str]]:
    if not isinstance(doc, dict):
        return []
    claims = doc.get("claims") or doc.get("items") or []
    if not isinstance(claims, list):
        claims = []
    if isinstance(doc.get("source_lineage"), list):
        claims = list(claims) + [{"source_lineage": doc["source_lineage"]}]
    edges: list[tuple[str, str]] = []
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        lin = claim.get("source_lineage") or claim.get("lineage") or claim.get("sources") or []
        if isinstance(lin, dict):
            lin = [lin]
        if isinstance(lin, list):
            for node in lin:
                art = as_artifact(node)
                if not art:
                    continue
                child_key = art.get("artifact_id")
                for parent in art.get("parents") or []:
                    parent_art = as_artifact(parent)
                    if parent_art and child_key:
                        pk = parent_art.get("artifact_id")
                        if pk:
                            edges.append((str(pk), str(child_key)))
        cid = claim.get("artifact_id") or claim.get("id")
        parents = claim.get("parents") or claim.get("derived_from") or []
        if cid and isinstance(parents, list):
            for parent in parents:
                parent_art = as_artifact(parent)
                if parent_art:
                    pk = parent_art.get("artifact_id")
                    if pk:
                        edges.append((str(pk), str(cid)))
    return edges


def candidate_reads_for_conclusion(
    cands: list[dict], conclusion_id: str
) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for cand in cands:
        agent = cand["agent_id"]
        specific: list[dict] = []
        for conc in cand.get("conclusions") or []:
            if not isinstance(conc, dict):
                continue
            cid = (
                conc.get("conclusion_id")
                or conc.get("id")
                or conc.get("item_id")
                or conc.get("canonical_mechanism")
            )
            if str(cid) != str(conclusion_id):
                continue
            lin = conc.get("lineage") or conc.get("sources") or conc.get("artifacts") or []
            if isinstance(lin, list):
                for item in lin:
                    art = as_artifact(item)
                    if art:
                        specific.append(art)
        if specific:
            out[agent] = specific
        elif cand.get("artifacts"):
            out[agent] = list(cand["artifacts"])
    return out


def build_live_scenario(
    conclusion: dict,
    per_agent_arts: dict[str, list[dict]],
    extra_edges: list[tuple[str, str]],
) -> dict | None:
    if len(per_agent_arts) < 2:
        return None
    artifacts: dict[str, dict] = {}
    agents = []
    for agent, arts in per_agent_arts.items():
        reads = []
        for art in arts:
            rec = dict(art)
            try:
                aid = str(
                    rec.get("artifact_id")
                    or rec.get("sha256")
                    or rec.get("path")
                    or artifact_identity(rec)
                )
            except ValueError:
                continue
            rec["artifact_id"] = aid
            rec.setdefault("parents", [])
            if isinstance(rec["parents"], str):
                rec["parents"] = [rec["parents"]]
            artifacts[aid] = rec
            reads.append(aid)
        if reads:
            agents.append({"id": agent, "reads": reads})
    if len(agents) < 2:
        return None
    for parent_key, child_key in extra_edges:
        if child_key not in artifacts:
            continue
        artifacts[child_key].setdefault("parents", [])
        if parent_key not in artifacts[child_key]["parents"]:
            artifacts[child_key]["parents"].append(parent_key)
        if parent_key not in artifacts:
            artifacts[parent_key] = {
                "artifact_id": parent_key,
                "path": parent_key,
                "parents": [],
            }
    return {
        "id": f"live-{conclusion['conclusion_id']}",
        "conclusion_id": conclusion["conclusion_id"],
        "conclusion": conclusion.get("text"),
        "expected_label": None,
        "agents": agents,
        "artifacts": list(artifacts.values()),
    }


def live_attributions(docs: dict[str, Any]) -> tuple[list[dict], list[dict], dict]:
    syn0010 = docs.get("SYN-0010")
    meta = extract_coefficient(syn0010)
    agreed = extract_agreed(syn0010)
    cands = extract_candidates(docs.get("SYN-0008"))
    edges = extract_lineage_edges(docs.get("CLAIM-REGISTRY"))
    attributed: list[dict] = []
    skipped: list[dict] = []
    if syn0010 is None:
        return attributed, skipped, {**meta, "agreed_n": 0, "reason": "SYN-0010-absent"}
    if not agreed:
        return (
            attributed,
            skipped,
            {**meta, "agreed_n": 0, "reason": "agreed-set-empty-or-unparsed"},
        )
    meta["agreed_n"] = len(agreed)
    meta["reason"] = "ok"
    if not cands:
        for conc in agreed:
            skipped.append(
                {
                    "conclusion_id": conc["conclusion_id"],
                    "reason": "SYN-0008-absent-or-unparsed",
                }
            )
        return attributed, skipped, meta
    for conc in agreed:
        per_agent = candidate_reads_for_conclusion(cands, conc["conclusion_id"])
        if conc.get("agents"):
            named = set(conc["agents"])
            filtered = {k: v for k, v in per_agent.items() if k in named}
            if len(filtered) >= 2:
                per_agent = filtered
        scenario = build_live_scenario(conc, per_agent, edges)
        if scenario is None:
            skipped.append(
                {
                    "conclusion_id": conc["conclusion_id"],
                    "reason": "fewer-than-2-agent-lineages",
                    "agents_with_lineage": sorted(per_agent.keys()),
                }
            )
            continue
        attributed.append(attribute_scenario(scenario, join="identity"))
    return attributed, skipped, meta
