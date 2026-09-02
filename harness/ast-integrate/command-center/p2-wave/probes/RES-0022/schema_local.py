"""Disk-only validator for the research-claim-record shim.

jsonschema 4.10 Draft7Validator follows $ref over the network to
ast-integrate.invalid and raises RefResolutionError. Preload the physical
schemas from disk so garbage is rejected and a receipt-shaped artifact can
pass without a rebuild circle.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver
from jsonschema.exceptions import RefResolutionError

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/research-claim-record.schema.json"
BASE = "https://ast-integrate.invalid/"
PINNED = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def _no_remote(uri: str):
    raise RefResolutionError(f"refusing network schema fetch: {uri}")


def load_store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for rel in PINNED:
        path = REPO / rel
        doc = json.loads(path.read_text(encoding="utf-8"))
        sid = str(doc.get("$id") or (BASE + rel))
        store[sid] = doc
        store[BASE + rel] = doc
    return store


def make_validator() -> Draft202012Validator:
    store = load_store()
    schema = store[BASE + SCHEMA_REL]
    resolver = RefResolver(
        base_uri=str(schema.get("$id") or (BASE + SCHEMA_REL)),
        referrer=schema,
        store=store,
        handlers={"https": _no_remote, "http": _no_remote},
    )
    return Draft202012Validator(schema, resolver=resolver)


def error_messages(doc: Any) -> list[str]:
    out: list[str] = []
    try:
        for err in make_validator().iter_errors(doc):
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            out.append(f"{loc}: {err.message}")
    except RefResolutionError as exc:
        out.append(f"<resolver>: {exc}")
    return sorted(out)


def garbage_rejected(validator: Draft202012Validator | None = None) -> int:
    v = validator or make_validator()
    n = 0
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"x": "x" * 200},
    ):
        try:
            if list(v.iter_errors(garbage)):
                n += 1
        except RefResolutionError:
            n += 1
    return n
