"""Stable identity, content hash, and field-level evidence deltas."""
from __future__ import annotations

import hashlib
import json
from typing import Any

CONTENT_FIELDS = ("title", "family", "mechanism", "body")


def canonical_id(raw_id: str, migration_map: dict[str, str]) -> str:
    """Follow alias rows to the frozen id. Cycles stop on first repeat."""
    seen: set[str] = set()
    cur = raw_id
    while cur in migration_map and cur not in seen:
        seen.add(cur)
        nxt = migration_map[cur]
        if not isinstance(nxt, str) or not nxt:
            break
        cur = nxt
    return cur


def content_payload(doc: dict[str, Any]) -> dict[str, Any]:
    return {k: doc.get(k) for k in CONTENT_FIELDS}


def content_hash(doc: dict[str, Any]) -> str:
    blob = json.dumps(content_payload(doc), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def field_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    delta: dict[str, Any] = {}
    for key in CONTENT_FIELDS:
        old, new = before.get(key), after.get(key)
        if old != new:
            delta[key] = {"from": old, "to": new}
    return delta
