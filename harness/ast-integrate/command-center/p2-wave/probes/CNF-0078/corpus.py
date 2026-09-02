#!/usr/bin/env python3
"""Load the CNF-0078 corpus: fixtures plus on-tree workflow_blueprint records."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURE = HERE / "fixtures" / "corpus.json"

LIBRARY_CANDIDATES = [
    "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "command-center/sources/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "command-center/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "command-center/libraries/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
]

ON_TREE_BLUEPRINT_SOURCES = [
    "command-center/p2-wave/probes/ARC-0010/registry.json",
]


def library_enumeration() -> dict:
    rows = []
    found = 0
    for rel in LIBRARY_CANDIDATES:
        p = REPO / rel
        exists = p.is_file()
        if exists:
            found += 1
        rows.append({"path": rel, "exists": exists, "bytes": p.stat().st_size if exists else 0})
    return {
        "searched": LIBRARY_CANDIDATES,
        "hits": rows,
        "files_found": found,
        "catalog_claimed_floor": 96,
        "note": (
            "09-WORKFLOW-BLUEPRINT-LIBRARY.json is absent on this worktree. "
            "A 96-entry distinctness claim cannot be confirmed or denied by "
            "counting that file."
        ),
    }


def _render_registry_blueprints() -> list[dict]:
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
                    "text": text,
                }
            )
    return out


def load_documents() -> list[dict]:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    docs = list(fixture["documents"])
    seen = {d["id"] for d in docs}
    for extra in _render_registry_blueprints():
        if extra["id"] in seen:
            continue
        docs.append(extra)
        seen.add(extra["id"])
    return docs


def by_id(docs: list[dict]) -> dict[str, dict]:
    return {d["id"]: d for d in docs}
