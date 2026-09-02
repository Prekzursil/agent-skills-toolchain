"""Resolve the catalog output_schema without a vacuous shim."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/audit-detector-control.schema.json"


def _disk_store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for rel in (
        "command-center/schema/audit-detector-control.schema.json",
        "platform/schema/artifact-class-profiles.schema.json",
        "platform/schema/receipt.schema.json",
    ):
        path = REPO / rel
        doc = json.loads(path.read_text(encoding="utf-8"))
        store["https://ast-integrate.invalid/" + rel] = doc
        store[path.resolve().as_uri()] = doc
        sid = doc.get("$id")
        if isinstance(sid, str) and sid:
            store[sid] = doc
    return store


def validator():
    lib = REPO / "platform" / "lib"
    if str(lib) not in sys.path:
        sys.path.insert(0, str(lib))
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    try:
        from schema_resolver import validator_for  # noqa: E402

        return validator_for(SCHEMA_REL)
    except Exception:
        pass
    import jsonschema

    store = _disk_store()
    base = str(schema.get("$id") or (REPO / SCHEMA_REL).resolve().as_uri())
    resolver = jsonschema.RefResolver(
        base_uri=base,
        referrer=schema,
        store=store,
    )
    return jsonschema.Draft202012Validator(schema, resolver=resolver)


def errors_for(doc: Any) -> list[str]:
    v = validator()
    out: list[str] = []
    for err in v.iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def rejects_garbage() -> int:
    v = validator()
    blobs = (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    )
    n = 0
    for blob in blobs:
        n += len(list(v.iter_errors(blob)))
    return n
