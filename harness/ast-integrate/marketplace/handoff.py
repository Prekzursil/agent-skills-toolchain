"""Build and validate install handoffs from a payload tree."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from plugin.payload import _iter_files, load_plugin_manifest, payload_digest


def schema_path() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "tools" / "plugin" / "schema" / "projection-map.schema.json"
        if cand.is_file():
            return cand
    return here.parent / "projection-map.schema.json"


def load_schema() -> dict[str, Any]:
    path = schema_path()
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "type": "object",
        "properties": {
            "projection_map": {
                "type": "object",
                "properties": {"schema_version": {"type": "integer"}, "entries": {"type": "array"}},
            }
        },
    }


def build_handoff(payload: Path, source: str = "direct") -> dict[str, Any]:
    payload = Path(payload)
    plugin = load_plugin_manifest(payload)
    name = str(plugin.get("name") or payload.name)
    digest = payload_digest(payload)
    entries = []
    for path in _iter_files(payload):
        rel = path.relative_to(payload).as_posix()
        entries.append({"source": rel, "dest": f"plugins/{name}/{rel}"})
    return {
        "declared_permissions": list(plugin.get("permissions") or [f"fs:write:plugins/{name}"]),
        "digest": {"alg": "sha256", "value": digest},
        "kind": "install-handoff",
        "payload_path": str(payload.resolve()),
        "plugin_name": name,
        "projection_map": {"entries": entries, "schema_version": 1},
        "schema_version": 1,
        "source": source,
        "transaction_id": str(uuid.uuid5(uuid.NAMESPACE_URL, name + digest)),
    }


def validate_handoff(handoff: Any) -> dict[str, Any]:
    if not isinstance(handoff, dict):
        raise TypeError("handoff must be a dict")
    if "payload_path" not in handoff:
        raise ValueError("handoff missing payload_path")
    if not isinstance(handoff.get("digest"), dict) or not handoff["digest"].get("value"):
        raise ValueError("handoff missing digest.value")
    projection = handoff.get("projection_map")
    if not isinstance(projection, dict) or not isinstance(projection.get("entries"), list):
        raise ValueError("handoff missing projection_map.entries")
    return handoff
