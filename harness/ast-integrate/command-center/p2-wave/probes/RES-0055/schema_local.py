"""Disk-only validator for command-center/schema/threat-model.schema.json.

jsonschema 4.10 follows $ref to https://ast-integrate.invalid and would
otherwise raise RefResolutionError on the network. Seed the store from
on-disk schema files and refuse http(s) retrieval.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator, Draft202012Validator
from jsonschema.exceptions import RefResolutionError
from jsonschema.validators import RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/threat-model.schema.json"
BASE = "https://ast-integrate.invalid/"
_STORE_RELS = (
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
    SCHEMA_REL,
)


def _refuse_remote(uri: str) -> Any:
    raise RefResolutionError(f"offline-registry: refused remote fetch of {uri}")


def _load(rel: str) -> dict[str, Any]:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def build_store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for meta in (Draft202012Validator.META_SCHEMA, Draft7Validator.META_SCHEMA):
        seeded = RefResolver.from_schema(meta)
        for uri, doc in seeded.store.items():
            store.setdefault(str(uri), doc)
    for rel in _STORE_RELS:
        doc = _load(rel)
        store[BASE + rel] = doc
        ident = doc.get("$id")
        if isinstance(ident, str) and ident:
            store[ident] = doc
    return store


def validator() -> Draft202012Validator:
    schema = _load(SCHEMA_REL)
    resolver = RefResolver(
        base_uri=str(schema.get("$id") or ""),
        referrer=schema,
        store=build_store(),
        cache_remote=False,
        handlers={"http": _refuse_remote, "https": _refuse_remote},
    )
    return Draft202012Validator(schema, resolver=resolver)


def errors(instance: Any) -> list[str]:
    out: list[str] = []
    try:
        for err in validator().iter_errors(instance):
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            out.append(f"{loc}: {err.message}")
    except Exception as exc:
        out.append(f"<resolver>: {type(exc).__name__}: {exc}")
    return sorted(out)


def fingerprint(errs: list[str]) -> str:
    blob = "\n".join(sorted(errs)).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:24]


def reject_empty_accept_live(doc: dict[str, Any]) -> tuple[bool, bool, list[str]]:
    empty_errs = errors({})
    live_errs = errors(doc)
    return bool(empty_errs), not live_errs, live_errs
