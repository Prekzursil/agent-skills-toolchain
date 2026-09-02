"""Disk-only binder for command-center/schema/council-design-note.schema.json.

jsonschema 4.10 on this worker still uses RefResolver and will otherwise
HTTP-GET https://ast-integrate.invalid (RefResolutionError). Store the
three on-disk $id documents and never touch the network.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/council-design-note.schema.json"
STORE_RELS = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def payload(doc: dict[str, Any]) -> dict[str, Any]:
    """Domain fields live under report (receipt_core additionalProperties=false)."""
    report = doc.get("report")
    return report if isinstance(report, dict) else doc


def _store() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for rel in STORE_RELS:
        path = REPO / rel
        raw = json.loads(path.read_text(encoding="utf-8"))
        out["https://ast-integrate.invalid/" + rel] = raw
        out[path.resolve().as_uri()] = raw
        sid = raw.get("$id")
        if isinstance(sid, str) and sid:
            out[sid] = raw
    return out


def validator() -> Draft202012Validator:
    lib = REPO / "platform" / "lib"
    if str(lib) not in sys.path:
        sys.path.insert(0, str(lib))
    try:
        from schema_resolver import validator_for  # noqa: WPS433

        return validator_for(SCHEMA_REL)
    except Exception:
        pass
    store = _store()
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    resolver = RefResolver.from_schema(schema, store=store)
    return Draft202012Validator(schema, resolver=resolver)


def errors(doc: Any) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)
