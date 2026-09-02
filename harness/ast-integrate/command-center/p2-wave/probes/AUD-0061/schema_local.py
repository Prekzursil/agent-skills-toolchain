"""Offline jsonschema resolution for AUD-0061 (no ast-integrate.invalid fetch).

jsonschema 4.10 Draft*Validator follows the catalog shim $ref onto the wire
and fails closed. G-1 json.loads the catalog path; this module is what the
emitter and named probes actually compile against, from disk.
"""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/audit-metric-baseline.schema.json"
SHIM_URI = (
    "https://ast-integrate.invalid/command-center/schema/"
    "audit-metric-baseline.schema.json"
)
BASE = "https://ast-integrate.invalid/"
STORE_FILES = {
    SHIM_URI: REPO / SCHEMA_REL,
    "https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json": (
        REPO / "platform/schema/artifact-class-profiles.schema.json"
    ),
    "https://ast-integrate.invalid/platform/schema/receipt.schema.json": (
        REPO / "platform/schema/receipt.schema.json"
    ),
}


def retrieve(uri: str) -> dict:
    if not uri.startswith(BASE):
        raise ValueError(f"refuses non-estate uri: {uri}")
    rel = uri[len(BASE) :].split("#", 1)[0]
    path = REPO / rel
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def load_store() -> dict:
    store = {}
    for uri, path in STORE_FILES.items():
        store[uri] = json.loads(path.read_text(encoding="utf-8"))
    return store


def validator() -> Draft202012Validator:
    store = load_store()
    schema = store[SHIM_URI]
    resolver = RefResolver(
        base_uri=SHIM_URI,
        referrer=schema,
        store=store,
        handlers={"https": retrieve, "http": retrieve},
    )
    return Draft202012Validator(schema, resolver=resolver)


def errors(doc) -> list[str]:
    out = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)
