"""Disk-only validator for command-center/schema/vendor-capability.schema.json.

The catalog file is a generated $ref shim. jsonschema 4.10 on this host follows
https://ast-integrate.invalid and would fetch the network. Seed a RefResolver
store from on-disk schema files so garbage is a ValidationError and a live
receipt can pass. Does not rebuild platform/schema.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/vendor-capability.schema.json"
STORE_RELS = (
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def _load(rel: str) -> dict[str, Any]:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def validator() -> Draft202012Validator:
    """Validate against the PHYSICAL vendor-capability definition.

    The generated shim delegates by $ref; the legacy RefResolver resolves that
    top-level $ref vacuously (garbage passed), so bind the physical
    ``$defs/vendor-capability`` subschema directly and resolve its inner
    receipt.schema.json references from the on-disk store.
    """
    docs: dict[str, Any] = {}
    resources: list[tuple[str, Resource]] = []
    for rel in STORE_RELS:
        doc = _load(rel)
        docs[rel] = doc
        resource = Resource.from_contents(doc)
        resources.append(("https://ast-integrate.invalid/" + rel, resource))
        ident = doc.get("$id")
        if isinstance(ident, str) and ident:
            resources.append((ident, resource))
    profiles = docs["platform/schema/artifact-class-profiles.schema.json"]
    subschema = (profiles.get("$defs") or {}).get("vendor-capability")
    if not isinstance(subschema, dict):
        raise KeyError("artifact-class-profiles.schema.json missing $defs/vendor-capability")
    registry = Registry().with_resources(resources)
    wrapped = dict(subschema)
    wrapped.setdefault("$id", str(profiles.get("$id") or "") + "#vendor-capability-direct")
    return Draft202012Validator(wrapped, registry=registry)


def errors(doc: Any) -> list[str]:
    out: list[str] = []
    try:
        for err in validator().iter_errors(doc):
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            out.append(f"{loc}: {err.message}")
    except Exception as exc:  # noqa: BLE001
        out.append(f"<resolver>: {type(exc).__name__}: {exc}")
    return sorted(out)
