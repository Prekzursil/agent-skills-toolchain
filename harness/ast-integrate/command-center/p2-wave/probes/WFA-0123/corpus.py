#!/usr/bin/env python3
"""Load live candidate rows from registry v2/v1 if present on this worktree."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REGISTRY_HINTS = (
    "command-center/wfa/WFA-0078-candidate-registry-v2.json",
    "command-center/wfa/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "command-center/08-WORKFLOW-CANDIDATE-REGISTRY.json",
)


def _rows_from_doc(doc: Any) -> list[dict]:
    if isinstance(doc, list):
        return [x for x in doc if isinstance(x, dict)]
    if not isinstance(doc, dict):
        return []
    for key in ("candidates", "records", "items", "workflows"):
        val = doc.get(key)
        if isinstance(val, list):
            return [x for x in val if isinstance(x, dict)]
    return []


def _normalize(rec: dict, source: str) -> dict:
    rid = rec.get("id") or rec.get("candidate_id") or rec.get("name")
    path = (
        rec.get("provenance")
        or rec.get("provenance_path")
        or rec.get("path")
        or rec.get("source_path")
    )
    return {
        "id": str(rid) if rid else "",
        "name": str(rec.get("name") or rid or ""),
        "does": str(rec.get("does") or rec.get("description") or ""),
        "mechanisms": rec.get("mechanisms") or rec.get("mechanism") or "",
        "classification": rec.get("classification") or rec.get("disposition") or "",
        "provenance": path or "",
        "license": rec.get("license") or rec.get("licence") or "",
        "license_file": rec.get("license_file") or rec.get("licence_file") or "",
        "kind": rec.get("kind") or rec.get("family") or "",
        "alias_of": rec.get("alias_of") or rec.get("alias_target") or rec.get("aliasOf"),
        "body": rec.get("body") or rec.get("does") or "",
        "source_artifact": source,
        "raw": rec,
    }


def load_live_registry(repo: Path) -> dict[str, Any]:
    found: list[dict] = []
    searched = []
    for rel in REGISTRY_HINTS:
        path = repo / rel
        searched.append({"path": rel, "exists": path.is_file()})
        if not path.is_file():
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rows = _rows_from_doc(doc)
        if not rows:
            continue
        found.append(
            {
                "path": rel,
                "bytes": path.stat().st_size,
                "n": len(rows),
                "records": [_normalize(r, rel) for r in rows if r.get("id") or r.get("name")],
            }
        )
    records: list[dict] = []
    source = None
    if found:
        # Prefer the largest candidate array (v2 if present and populated).
        found.sort(key=lambda x: x["n"], reverse=True)
        source = found[0]
        records = source["records"]
    return {
        "searched": searched,
        "hits": [{"path": h["path"], "n": h["n"], "bytes": h["bytes"]} for h in found],
        "source_path": None if source is None else source["path"],
        "records": records,
        "live_raw_count": len(records),
        "registry_present": bool(records),
        "catalog_declared_raw": 284,
        "catalog_declared_raw_is_measured": False,
    }
