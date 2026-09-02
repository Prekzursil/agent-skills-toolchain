"""Resolve dedup-report $ref onto disk (jsonschema 4.10 RefResolver).

The catalog shim $ref's https://ast-integrate.invalid/... which is not a
network host. Fetching it would make schema_rejects_garbage a detector that
never actually constrains. Map those $id values to the physical files under
platform/schema/.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema.exceptions import RefResolutionError

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/dedup-report.schema.json"
STORE_RELS = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"unit_id": "SYN-0017", "state": "SUCCESS"},
)


def _load(rel: str) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def _refuse_remote(uri: str):
    raise RefResolutionError(f"offline-registry: refused remote fetch of {uri}")


def _store() -> dict:
    store: dict = {}
    for rel in STORE_RELS:
        data = _load(rel)
        uri = "https://ast-integrate.invalid/" + rel
        store[uri] = data
        sid = data.get("$id")
        if isinstance(sid, str) and sid:
            store[sid] = data
    return store


def validator() -> jsonschema.Draft202012Validator:
    schema = _load(SCHEMA_REL)
    store = _store()
    base = schema.get("$id") or ("https://ast-integrate.invalid/" + SCHEMA_REL)
    resolver = jsonschema.RefResolver(
        base_uri=str(base),
        referrer=schema,
        store=store,
        handlers={"http": _refuse_remote, "https": _refuse_remote},
    )
    return jsonschema.Draft202012Validator(schema, resolver=resolver)


def errors(doc: object) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def schema_rejects_garbage() -> tuple[bool, str]:
    v = validator()
    for g in GARBAGE:
        if v.is_valid(g):
            return False, f"schema accepted garbage {list(g)[:2]!r}"
    return True, "3/3 garbage rejected"


def report_of(doc: dict) -> dict:
    rep = doc.get("report") if isinstance(doc, dict) else None
    return rep if isinstance(rep, dict) else {}


def pick(doc: dict, key: str, default: Any = None) -> Any:
    """Domain fields live under report (receipt_core additionalProperties=false)."""
    rep = report_of(doc)
    if isinstance(rep, dict) and key in rep and rep[key] is not None:
        return rep[key]
    if isinstance(doc, dict) and key in doc and doc[key] is not None:
        return doc[key]
    return default
