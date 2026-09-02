"""Offline docs_conformance_report validator (jsonschema 4.10, no network)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
BASE_URI = "https://ast-integrate.invalid/"
CATALOG_SCHEMA = (
    "command-center/schema/receipt.schema.json#/$defs/docs_conformance_report"
)
PHYSICAL = (
    "command-center/schema/receipt.schema.json",
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\n{command}".encode("utf-8")).hexdigest()


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _store() -> dict[str, dict[str, Any]]:
    store: dict[str, dict[str, Any]] = {}
    for rel in PHYSICAL:
        data = json.loads((REPO / rel).read_text(encoding="utf-8"))
        store[BASE_URI + rel] = data
        ident = data.get("$id")
        if isinstance(ident, str) and ident:
            store[ident] = data
    return store


def _https_handler(uri: str) -> dict[str, Any]:
    if not uri.startswith(BASE_URI):
        raise ValueError(f"refusing non-local schema uri: {uri}")
    rel = uri[len(BASE_URI) :].split("#", 1)[0]
    path = (REPO / rel).resolve()
    root = REPO.resolve()
    if root not in path.parents and path != root:
        raise ValueError(f"schema uri escapes repo: {uri}")
    if not path.is_file():
        raise ValueError(f"schema uri missing on disk: {uri}")
    return json.loads(path.read_text(encoding="utf-8"))


def validator() -> Draft202012Validator:
    store = _store()
    shim = store[BASE_URI + "command-center/schema/receipt.schema.json"]
    ref = {"$ref": BASE_URI + CATALOG_SCHEMA}
    resolver = RefResolver(
        base_uri=str(shim.get("$id") or (BASE_URI + "command-center/schema/receipt.schema.json")),
        referrer=shim,
        store=store,
        handlers={"https": _https_handler, "http": _https_handler},
    )
    return Draft202012Validator(ref, resolver=resolver)


def iter_errors(doc: object) -> list:
    return sorted(validator().iter_errors(doc), key=lambda e: list(e.path))


def garbage_accepted() -> object | None:
    v = validator()
    for garbage in (
        {},
        {"schema_version": 1, "unit_id": "TST-0252", "state": "SUCCESS"},
        {"report": {"kind": "docs_conformance_report"}},
        {"report": {"kind": "cache_report"}},
    ):
        if not list(v.iter_errors(garbage)):
            return garbage
    return None
