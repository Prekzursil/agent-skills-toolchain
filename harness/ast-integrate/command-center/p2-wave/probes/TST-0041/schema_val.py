"""Offline validator for command-center/schema/conformance-report.schema.json.

Draft7Validator against the shim $ref tries HTTPS to ast-integrate.invalid
and raises RefResolutionError on this Linux worktree. Resolve $ref from disk.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.validators import RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/conformance-report.schema.json"
STORE_RELS = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def fingerprint(method: str, command: str) -> str:
    raw = f"{method}|{command}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def schema_store() -> dict:
    store: dict = {}
    for rel in STORE_RELS:
        data = json.loads((REPO / rel).read_text(encoding="utf-8"))
        store["https://ast-integrate.invalid/" + rel] = data
        store["file:///C:/Users/Prekzursil/source/ast-integrate/" + rel] = data
        store["file:///home/prekzursil/p2-g1/" + rel] = data
        ident = data.get("$id")
        if isinstance(ident, str) and ident:
            store[ident] = data
    return store


def _refuse(uri: str):
    raise ValueError(f"offline-refused {uri}")


def validator():
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    store = schema_store()
    profiles = json.loads(
        (REPO / "platform/schema/artifact-class-profiles.schema.json").read_text(
            encoding="utf-8"
        )
    )
    target = schema
    defs = profiles.get("$defs") if isinstance(profiles, dict) else None
    if isinstance(defs, dict) and isinstance(defs.get("conformance-report"), dict):
        target = dict(defs["conformance-report"])
        target["$defs"] = defs
    resolver = RefResolver(
        base_uri="https://ast-integrate.invalid/" + SCHEMA_REL,
        referrer=schema,
        store=store,
        handlers={"http": _refuse, "https": _refuse, "file": _refuse},
    )
    return Draft202012Validator(target, resolver=resolver)


def schema_errors(doc) -> list[str]:
    out = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)
