"""Resolve detector-control $ref onto disk (jsonschema 4.10, no network)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema.exceptions import RefResolutionError

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/detector-control.schema.json"
PROFILES = "platform/schema/artifact-class-profiles.schema.json"
RECEIPT = "platform/schema/receipt.schema.json"


def _refuse(uri: str) -> Any:
    raise RefResolutionError(f"offline-refused {uri}")


def load_json(rel: str) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def _aliases(rel: str, doc: dict) -> dict:
    store = {
        "https://ast-integrate.invalid/" + rel: doc,
        "file:///C:/Users/Prekzursil/source/ast-integrate/" + rel: doc,
        "file:///home/prekzursil/p2-g1/" + rel: doc,
    }
    ident = doc.get("$id")
    if isinstance(ident, str) and ident:
        store[ident] = doc
    return store


def validator() -> jsonschema.Draft7Validator:
    shim = load_json(SCHEMA_REL)
    profiles = load_json(PROFILES)
    receipt = load_json(RECEIPT)
    store = {}
    store.update(_aliases(SCHEMA_REL, shim))
    store.update(_aliases(PROFILES, profiles))
    store.update(_aliases(RECEIPT, receipt))
    target = shim
    defs = profiles.get("$defs") if isinstance(profiles, dict) else None
    if isinstance(defs, dict) and isinstance(defs.get("detector-control"), dict):
        target = dict(defs["detector-control"])
        extra = dict(defs)
        extra.update(shim.get("$defs") or {})
        target["$defs"] = extra
    resolver = jsonschema.RefResolver(
        base_uri="https://ast-integrate.invalid/" + SCHEMA_REL,
        referrer=shim,
        store=store,
        cache_remote=False,
        handlers={"http": _refuse, "https": _refuse, "file": _refuse},
    )
    return jsonschema.Draft7Validator(target, resolver=resolver)


def report_body(doc: dict) -> dict:
    """Domain fields live under report (receipt_core additionalProperties: false)."""
    inner = doc.get("report")
    if isinstance(inner, dict) and isinstance(inner.get("gates"), list):
        return inner
    return doc


def schema_errors(doc: Any) -> list[str]:
    out: list[str] = []
    for err in sorted(validator().iter_errors(doc), key=lambda e: list(e.path)):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return out


def garbage_rejected() -> bool:
    v = validator()
    for item in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"kind": "detector-control", "state": "SUCCESS"},
    ):
        if not list(v.iter_errors(item)):
            return False
    return True
