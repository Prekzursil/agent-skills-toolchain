#!/usr/bin/env python3
"""Disk-only jsonschema 4.10 resolver for the evidence-integrity-report shim."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator, Draft202012Validator
from jsonschema.exceptions import RefResolutionError
from jsonschema.validators import RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/evidence-integrity-report.schema.json"
BASE = "https://ast-integrate.invalid/"


def _refuse_remote(uri: str) -> Any:
    raise RefResolutionError(f"offline-registry: refused remote fetch of {uri}")


def build_store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for meta in (Draft202012Validator.META_SCHEMA, Draft7Validator.META_SCHEMA):
        seeded = RefResolver.from_schema(meta)
        for uri, doc in seeded.store.items():
            store.setdefault(str(uri), doc)
    for root in (REPO / "platform" / "schema", REPO / "command-center" / "schema"):
        if not root.is_dir():
            continue
        for path in root.rglob("*.json"):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(doc, dict):
                continue
            rel = path.relative_to(REPO).as_posix()
            store[BASE + rel] = doc
            ident = doc.get("$id")
            if isinstance(ident, str) and ident:
                store[ident] = doc
    return store


def validator_for(rel: str = SCHEMA_REL) -> Draft202012Validator:
    schema = json.loads((REPO / rel).read_text(encoding="utf-8"))
    store = build_store()
    resolver = RefResolver(
        base_uri=str(schema.get("$id") or ""),
        referrer=schema,
        store=store,
        cache_remote=False,
        handlers={"http": _refuse_remote, "https": _refuse_remote},
    )
    return Draft202012Validator(schema, resolver=resolver)


def errors_of(instance: Any, rel: str = SCHEMA_REL) -> list[str]:
    out: list[str] = []
    try:
        for err in validator_for(rel).iter_errors(instance):
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            out.append(f"{loc}: {err.message}")
    except Exception as exc:
        out.append(f"<resolver>: {type(exc).__name__}: {exc}")
    return sorted(out)
