"""Offline validator for the audit-inventory catalog shim.

jsonschema 4.10.3 follows $ref by fetching https://ast-integrate.invalid/
which is not a host. Map those $id URIs onto repo files. Bare
Draft7Validator on the shim is either Unresolvable or vacuous.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/audit-inventory.schema.json"
STORE_RELS = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def load_schema() -> dict[str, Any]:
    return json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))


def load_store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for rel in STORE_RELS:
        doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
        sid = doc.get("$id")
        if isinstance(sid, str) and sid:
            store[sid] = doc
            store[sid.split("#", 1)[0]] = doc
        store["https://ast-integrate.invalid/" + rel] = doc
        store["http://ast-integrate.invalid/" + rel] = doc
        store[rel] = doc
        store["/" + rel] = doc
        uri = (REPO / rel).resolve().as_uri()
        store[uri] = doc
        store[uri.replace("file:///", "file://")] = doc
    return store


def _refuse_remote(uri: str) -> dict:
    raise ValueError(f"refusing remote schema fetch: {uri}")


def validator() -> Draft7Validator:
    schema = load_schema()
    resolver = RefResolver(
        base_uri=str(schema.get("$id") or ""),
        referrer=schema,
        store=load_store(),
        handlers={"https": _refuse_remote, "http": _refuse_remote},
    )
    return Draft7Validator(schema, resolver=resolver)


class _Err:
    def __init__(self, message: str) -> None:
        self.message = message
        self.absolute_path = ()
        self.path = ()


def iter_errors(doc: object) -> list:
    errs = list(validator().iter_errors(doc))
    if not errs and (not isinstance(doc, dict) or "unit_id" not in doc):
        return [_Err("missing unit_id (garbage/empty)")]
    return errs


def schema_error_strings(doc: object) -> list[str]:
    out: list[str] = []
    for err in iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path)
        out.append((loc + ": " if loc else "") + err.message)
    return out
