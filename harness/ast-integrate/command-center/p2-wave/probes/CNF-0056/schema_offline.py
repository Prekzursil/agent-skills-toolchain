"""Validate against regression-delta.schema.json with disk-only $ref resolution.

jsonschema 4.10.3 Draft7Validator follows https://ast-integrate.invalid/...
over the network. That TLD does not resolve. This module loads the shim and
its physical targets into a RefResolver store so validation stays offline.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/regression-delta.schema.json"
STORE_FILES = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def schema_store(repo: Path | None = None) -> dict[str, Any]:
    root = repo or REPO
    store: dict[str, Any] = {}
    for rel in STORE_FILES:
        data = json.loads((root / rel).read_text(encoding="utf-8"))
        store["https://ast-integrate.invalid/" + rel] = data
        ident = data.get("$id")
        if isinstance(ident, str) and ident:
            store[ident] = data
    return store


def load_schema(repo: Path | None = None) -> dict[str, Any]:
    root = repo or REPO
    return json.loads((root / SCHEMA_REL).read_text(encoding="utf-8"))


def validator(repo: Path | None = None) -> jsonschema.Draft7Validator:
    root = repo or REPO
    schema = load_schema(root)
    resolver = jsonschema.RefResolver(
        base_uri=str(
            schema.get("$id") or ("https://ast-integrate.invalid/" + SCHEMA_REL)
        ),
        referrer=schema,
        store=schema_store(root),
    )
    return jsonschema.Draft7Validator(schema, resolver=resolver)


def validate_doc(doc: Any, repo: Path | None = None) -> list[str]:
    errors: list[str] = []
    for err in validator(repo).iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        errors.append(f"{loc}: {err.message}")
    return errors


def artifact_payload(doc: dict[str, Any]) -> dict[str, Any]:
    """Domain fields live under report (receipt_core additionalProperties=false)."""
    report = doc.get("report")
    if isinstance(report, dict) and (
        report.get("kind") == "regression-delta" or "before" in report
    ):
        return report
    return doc
