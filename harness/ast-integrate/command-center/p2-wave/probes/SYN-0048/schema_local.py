"""Disk-only validators for SYN-0048. Never fetch ast-integrate.invalid.

jsonschema 4.10 Draft7Validator follows the catalog shim $ref over HTTPS and
raises RefResolutionError. G-1 only json.loads the artifact. Named probes and
emit use this module: the catalog receipt profile plus local teeth that require
every deferred item to carry a reopen_trigger. Do not rebuild platform/schema
(ADV circle).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema.exceptions import RefResolutionError

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/handoff-package.schema.json"
STORE_RELS = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)

TEETH = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["unit_id", "state", "sentinel", "report"],
    "properties": {
        "unit_id": {"const": "SYN-0048"},
        "state": {"enum": ["SUCCESS", "FAILED", "BLOCKED", "SEVERED", "TIMEOUT"]},
        "sentinel": {"type": "string", "minLength": 8},
        "report": {
            "type": "object",
            "required": [
                "kind",
                "in_flight",
                "deferred_items",
                "supersession_edges",
                "next_action",
            ],
            "properties": {
                "kind": {"const": "handoff-package"},
                "deferred_items": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "required": ["id", "reason", "reopen_trigger"],
                        "properties": {
                            "id": {"type": "string", "minLength": 1},
                            "reason": {"type": "string", "minLength": 1},
                            "reopen_trigger": {
                                "type": "object",
                                "required": ["kind", "predicate"],
                                "properties": {
                                    "kind": {"type": "string", "minLength": 1},
                                    "predicate": {"type": "string", "minLength": 1},
                                },
                            },
                        },
                    },
                },
                "supersession_edges": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "required": [
                            "old_id",
                            "new_id",
                            "read_back",
                            "old_superseded_by",
                            "new_valid_as_of",
                        ],
                        "properties": {
                            "read_back": {"const": True},
                        },
                    },
                },
                "next_action": {
                    "type": "object",
                    "required": ["kind", "instruction"],
                    "properties": {
                        "kind": {"type": "string", "minLength": 1},
                        "instruction": {"type": "string", "minLength": 1},
                    },
                },
            },
        },
    },
}


def _refuse_remote(uri: str) -> Any:
    raise RefResolutionError(f"offline-registry: refused remote fetch of {uri}")


def schema_store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for rel in STORE_RELS:
        path = REPO / rel
        if not path.is_file():
            raise FileNotFoundError(rel)
        doc = json.loads(path.read_text(encoding="utf-8"))
        store["https://ast-integrate.invalid/" + rel] = doc
        ident = doc.get("$id")
        if isinstance(ident, str) and ident:
            store[ident] = doc
    return store


def catalog_validator() -> jsonschema.Draft202012Validator:
    shim = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    resolver = jsonschema.RefResolver.from_schema(
        shim,
        store=schema_store(),
        handlers={"http": _refuse_remote, "https": _refuse_remote},
    )
    return jsonschema.Draft202012Validator(shim, resolver=resolver)


def teeth_validator() -> jsonschema.Draft7Validator:
    jsonschema.Draft7Validator.check_schema(TEETH)
    return jsonschema.Draft7Validator(TEETH)


def _fmt(err: Any) -> str:
    loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
    return f"{loc}: {err.message}"


def catalog_errors(instance: Any) -> list[str]:
    out: list[str] = []
    try:
        for err in catalog_validator().iter_errors(instance):
            out.append(_fmt(err))
    except Exception as exc:
        out.append(f"<catalog-resolver>: {type(exc).__name__}: {exc}")
    return sorted(out)


def teeth_errors(instance: Any) -> list[str]:
    return sorted(_fmt(err) for err in teeth_validator().iter_errors(instance))


def error_list(instance: Any) -> list[str]:
    """Catalog receipt profile plus deferred-item teeth. Empty list = valid."""
    return sorted(set(catalog_errors(instance) + teeth_errors(instance)))
