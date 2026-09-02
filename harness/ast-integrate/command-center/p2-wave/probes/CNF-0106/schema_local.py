"""Resolve catalog $ref shims from disk. Never fetch ast-integrate.invalid."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/hermeticity-report.schema.json"
PHYSICAL = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def store() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for rel in PHYSICAL:
        doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
        out["https://ast-integrate.invalid/" + rel] = doc
        sid = doc.get("$id")
        if isinstance(sid, str) and sid:
            out[sid] = doc
    return out


def validator() -> Draft7Validator:
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    base = str(schema.get("$id") or ("https://ast-integrate.invalid/" + SCHEMA_REL))
    resolver = RefResolver(base_uri=base, referrer=schema, store=store())
    return Draft7Validator(schema, resolver=resolver)


def errors(doc: Any) -> list[str]:
    return [
        f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in sorted(validator().iter_errors(doc), key=lambda e: list(e.path))
    ]
