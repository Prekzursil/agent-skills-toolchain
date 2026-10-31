"""Mechanism fingerprints that ignore identifier spelling."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any


def rename_identifiers(workflow: dict[str, Any], suffix: str) -> dict[str, Any]:
    stages = [str(s) + suffix for s in (workflow.get("stages") or [])]
    mapping = {str(old): str(old) + suffix for old in (workflow.get("stages") or [])}
    edges = [
        [mapping.get(str(a), str(a) + suffix), mapping.get(str(b), str(b) + suffix)]
        for a, b in (workflow.get("edges") or [])
    ]
    return {"stages": stages, "edges": edges}


def mechanism_fingerprint(workflow: dict[str, Any]) -> str:
    stages = tuple(workflow.get("stages") or [])
    edges = tuple(tuple(e) for e in (workflow.get("edges") or []))
    # Drop identifier tokens; keep topology length and edge pattern by index.
    index = {name: i for i, name in enumerate(stages)}
    rel_edges = tuple(
        (index.get(a, -1), index.get(b, -1)) for a, b in edges
    )
    payload = json.dumps({"n": len(stages), "e": rel_edges}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
