"""Disk-only Draft202012 validator for architecture-review.schema.json.

The catalog shim $ref is https://ast-integrate.invalid/...; jsonschema 4.10
tries the network and raises RefResolutionError. This module maps that
prefix onto files under the repo root and never opens a socket.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PREFIX = "https://ast-integrate.invalid/"
SCHEMA_REL = "command-center/schema/architecture-review.schema.json"
GOOD_REL = (
    "command-center/p2-wave/probes/ARC-0047/fixtures/schema/known-good-review.json"
)


def _disk_handler(uri: str) -> Any:
    if uri.startswith("https://json-schema.org/"):
        # Meta-schema: let jsonschema use its bundled copy via store.
        raise jsonschema.exceptions.RefResolutionError(f"meta-schema not in disk store: {uri}")
    if not uri.startswith(PREFIX):
        raise jsonschema.exceptions.RefResolutionError(f"refusing non-local schema uri: {uri}")
    rel = uri[len(PREFIX) :].split("#", 1)[0]
    path = (REPO / rel).resolve()
    root = REPO.resolve()
    if not str(path).startswith(str(root) + "/"):
        raise jsonschema.exceptions.RefResolutionError(f"schema uri escapes repo: {uri}")
    if not path.is_file():
        raise jsonschema.exceptions.RefResolutionError(f"schema file missing: {rel}")
    return json.loads(path.read_text(encoding="utf-8"))


def _store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    files = [
        REPO / SCHEMA_REL,
        REPO / "platform/schema/artifact-class-profiles.schema.json",
        REPO / "platform/schema/receipt.schema.json",
    ]
    for path in files:
        doc = json.loads(path.read_text(encoding="utf-8"))
        rid = str(doc.get("$id") or "")
        if rid:
            store[rid] = doc
        store[PREFIX + path.relative_to(REPO).as_posix()] = doc
    return store


def review_validator() -> Draft202012Validator:
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    resolver = RefResolver.from_schema(
        schema,
        store=_store(),
        handlers={"https": _disk_handler, "http": _disk_handler},
        cache_remote=False,
    )
    return Draft202012Validator(schema, resolver=resolver)


def error_messages(doc: Any, validator: Draft202012Validator | None = None) -> list[str]:
    v = validator or review_validator()
    out: list[str] = []
    try:
        for err in v.iter_errors(doc):
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            out.append(f"{loc}: {err.message}")
    except jsonschema.exceptions.RefResolutionError as exc:
        out.append(f"<ref>: {exc}")
    return sorted(out)


def rejects(doc: Any, validator: Draft202012Validator | None = None) -> bool:
    """True (FIRE) when the schema refuses the document."""
    return bool(error_messages(doc, validator))
