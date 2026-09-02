"""Disk-only jsonschema resolver for command-center/schema shims.

The catalog output_schema is a $ref shim whose $id lives under
https://ast-integrate.invalid/. jsonschema 4.10 otherwise tries the network.
This module maps those URIs onto files under the repo root. No retrieval
leaves the filesystem.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema.exceptions import RefResolutionError

REPO = Path(__file__).resolve().parents[3]
SCHEMA_REL = "command-center/schema/security-report.schema.json"
_STORE_RELS = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RefResolutionError(f"schema is not an object: {path}")
    return data


def _no_remote(uri: str) -> Any:
    raise RefResolutionError(f"refusing network retrieve: {uri}")


def disk_store(repo: Path | None = None) -> dict[str, Any]:
    root = Path(repo or REPO)
    store: dict[str, Any] = {}
    for rel in _STORE_RELS:
        path = root / rel
        if not path.is_file():
            raise RefResolutionError(f"schema file missing: {rel}")
        doc = _load(path)
        sid = doc.get("$id")
        if isinstance(sid, str) and sid:
            store[sid] = doc
    return store


def validator_for(repo: Path | None = None, schema_rel: str = SCHEMA_REL):
    root = Path(repo or REPO)
    schema_path = root / schema_rel
    schema = _load(schema_path)
    store = disk_store(root)
    sid = schema.get("$id")
    if isinstance(sid, str) and sid:
        store[sid] = schema
    resolver = jsonschema.RefResolver(
        base_uri=str(sid or schema_path.as_uri()),
        referrer=schema,
        store=store,
        handlers={"http": _no_remote, "https": _no_remote},
    )
    cls = getattr(jsonschema, "Draft202012Validator", jsonschema.Draft7Validator)
    return cls(schema, resolver=resolver)


def iter_errors(doc: Any, repo: Path | None = None, schema_rel: str = SCHEMA_REL):
    validator = validator_for(repo, schema_rel)
    return sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
