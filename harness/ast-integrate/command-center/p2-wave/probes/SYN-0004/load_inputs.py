"""Load live SYN-0004 inputs. Absent files are recorded, never invented."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from constants import CLAIM_REGISTRY_REL, HIERARCHY_REL, REPO, RISK_REGISTER_REL

SEV_TOKEN = re.compile(r"\bP[0-3]\b")


def _present(rel: str) -> bool:
    return (REPO / rel).is_file() and (REPO / rel).stat().st_size > 0


def _read_json(rel: str) -> tuple[bool, Any, str | None]:
    path = REPO / rel
    if not path.is_file() or path.stat().st_size <= 0:
        return False, None, "absent"
    try:
        return True, json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return True, None, f"{type(exc).__name__}: {exc}"


def load_claim_index() -> dict[str, str]:
    present, doc, err = _read_json(CLAIM_REGISTRY_REL)
    if not present or err or not isinstance(doc, dict):
        return {}
    out: dict[str, str] = {}
    claims = doc.get("claims")
    if isinstance(claims, list):
        seq = claims
    elif isinstance(claims, dict):
        seq = [
            {"id": k, **v} if isinstance(v, dict) else {"id": k}
            for k, v in claims.items()
        ]
    else:
        seq = []
        for key in ("records", "items", "entries"):
            if isinstance(doc.get(key), list):
                seq = doc[key]
                break
    for item in seq:
        if not isinstance(item, dict):
            continue
        cid = item.get("id") or item.get("claim_id")
        sev = item.get("severity") or item.get("recorded_severity")
        if isinstance(cid, str) and cid.strip() and sev is not None:
            out[cid.strip()] = sev
    return out


def overlay_claim_severities(doc: dict, index: dict[str, str]) -> dict:
    if not index:
        return doc
    cloned = json.loads(json.dumps(doc))
    nodes = cloned.get("nodes")
    if not isinstance(nodes, list) and isinstance(cloned.get("graph"), dict):
        nodes = cloned["graph"].get("nodes")
    if not isinstance(nodes, list):
        return cloned
    for node in nodes:
        if not isinstance(node, dict):
            continue
        ids = []
        cid = node.get("claim_id") or node.get("id")
        if isinstance(cid, str):
            ids.append(cid)
        extra = node.get("claim_ids") or []
        if isinstance(extra, list):
            ids.extend(x for x in extra if isinstance(x, str))
        for cid in ids:
            if cid in index and not node.get("severity") and not node.get(
                "recorded_severity"
            ):
                node["severity"] = index[cid]
                break
            if cid in index and node.get("severity") in (None, ""):
                node["severity"] = index[cid]
                break
    return cloned


def scan_risk_register() -> dict:
    rel = RISK_REGISTER_REL
    path = REPO / rel
    if not path.is_file():
        return {"path": rel, "present": False, "bytes": 0, "tokens": []}
    raw = path.read_text(encoding="utf-8", errors="replace")
    tokens = sorted(set(SEV_TOKEN.findall(raw)))
    return {
        "path": rel,
        "present": True,
        "bytes": len(raw.encode("utf-8")),
        "tokens": tokens,
        "line_count": raw.count("\n") + (0 if raw.endswith("\n") or not raw else 1),
    }


def load_live_hierarchy() -> dict:
    present, doc, err = _read_json(HIERARCHY_REL)
    info = {
        "path": HIERARCHY_REL,
        "present": present,
        "parse_error": err,
        "document": doc if isinstance(doc, dict) else None,
    }
    claims_present = _present(CLAIM_REGISTRY_REL)
    info["claim_registry"] = {
        "path": CLAIM_REGISTRY_REL,
        "present": claims_present,
        "index_size": 0,
    }
    if present and isinstance(doc, dict) and not err:
        index = load_claim_index()
        info["claim_registry"]["index_size"] = len(index)
        info["document"] = overlay_claim_severities(doc, index)
    info["risk_register"] = scan_risk_register()
    return info
