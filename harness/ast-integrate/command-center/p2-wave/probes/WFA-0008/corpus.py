#!/usr/bin/env python3
"""Load the WFA-0008 corpus: planted controls plus any on-tree registries."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLANTED = HERE / "fixtures" / "planted.json"

REGISTRY_CANDIDATES = [
    "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "command-center/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "command-center/sources/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "command-center/wfa/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "command-center/libraries/08-WORKFLOW-CANDIDATE-REGISTRY.json",
]

BLUEPRINT_CANDIDATES = [
    "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "command-center/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "command-center/sources/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "command-center/wfa/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "command-center/libraries/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
]

LEXICAL_SCAN_CANDIDATES = [
    "command-center/wfa/WFA-0007-lexical-duplicate-scan.json",
]

ON_TREE_BLUEPRINT_SOURCES = [
    "command-center/p2-wave/probes/ARC-0010/registry.json",
    "command-center/p2-wave/probes/ARC-0010/registry.json",
]


def _exists_row(rel: str) -> dict:
    path = REPO / rel
    exists = path.is_file()
    return {
        "path": rel,
        "exists": exists,
        "bytes": path.stat().st_size if exists else 0,
    }


def inventory() -> dict:
    reg = [_exists_row(p) for p in REGISTRY_CANDIDATES]
    bp = [_exists_row(p) for p in BLUEPRINT_CANDIDATES]
    lex = [_exists_row(p) for p in LEXICAL_SCAN_CANDIDATES]
    return {
        "candidate_registry": {
            "searched": REGISTRY_CANDIDATES,
            "hits": reg,
            "files_found": sum(1 for r in reg if r["exists"]),
            "catalog_claimed": 284,
        },
        "blueprint_library": {
            "searched": BLUEPRINT_CANDIDATES,
            "hits": bp,
            "files_found": sum(1 for r in bp if r["exists"]),
            "catalog_claimed": 108,
        },
        "wfa0007_lexical_scan": {
            "searched": LEXICAL_SCAN_CANDIDATES,
            "hits": lex,
            "files_found": sum(1 for r in lex if r["exists"]),
        },
    }


def _render_ontree() -> list[dict]:
    out: list[dict] = []
    for rel in ON_TREE_BLUEPRINT_SOURCES:
        path = REPO / rel
        if not path.is_file():
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        for entry in doc.get("entries") or []:
            if not isinstance(entry, dict):
                continue
            if entry.get("kind") != "workflow_blueprint":
                continue
            eid = str(entry.get("id") or "unknown")
            text = json.dumps(entry, sort_keys=True, ensure_ascii=True)
            out.append(
                {
                    "id": f"ontree.{eid}",
                    "role": "on-tree",
                    "planted": False,
                    "class": None,
                    "origin": rel,
                    "name": eid,
                    "mechanisms": [],
                    "text": text,
                }
            )
    return out


def load_documents() -> list[dict]:
    fixture = json.loads(PLANTED.read_text(encoding="utf-8"))
    docs = list(fixture["documents"])
    seen = {d["id"] for d in docs}
    for extra in _render_ontree():
        if extra["id"] in seen:
            continue
        docs.append(extra)
        seen.add(extra["id"])
    return docs


def by_id(docs: list[dict]) -> dict[str, dict]:
    return {d["id"]: d for d in docs}


def scoring_text(doc: dict) -> str:
    name = str(doc.get("name") or "")
    mechanisms = " ".join(str(m) for m in (doc.get("mechanisms") or []))
    body = str(doc.get("text") or doc.get("does") or "")
    return " ".join(p for p in (name, body, mechanisms) if p)


load_documents = load_documents
by_id = by_id
scoring_text = scoring_text
load_documents = load_documents
load_documents = load_documents
load_documents = load_documents
