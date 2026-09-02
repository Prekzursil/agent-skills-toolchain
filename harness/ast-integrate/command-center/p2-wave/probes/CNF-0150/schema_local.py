"""Resolve the reproduction-matrix $ref shim from disk (no network).

jsonschema 4.10 on this host takes resolver=, not registry=. schema_resolver.validator_for
is written for jsonschema>=4.18 and TypeErrors here. This store is the same three files
CNF-0024/ARC-0106 use.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/reproduction-matrix.schema.json"
STORE_RELS = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode("utf-8")).hexdigest()


def _store() -> dict:
    out: dict = {}
    for rel in STORE_RELS:
        path = REPO / rel
        if not path.is_file():
            continue
        body = json.loads(path.read_text(encoding="utf-8"))
        sid = body.get("$id")
        if isinstance(sid, str) and sid:
            out[sid] = body
            out[sid.split("#", 1)[0]] = body
        out["https://ast-integrate.invalid/" + rel] = body
        out["http://ast-integrate.invalid/" + rel] = body
        out[rel] = body
        uri = path.resolve().as_uri()
        out[uri] = body
    return out


def validator():
    path = REPO / SCHEMA_REL
    schema = json.loads(path.read_text(encoding="utf-8"))
    resolver = jsonschema.RefResolver.from_schema(schema, store=_store())
    return jsonschema.Draft202012Validator(schema, resolver=resolver)


class _Err:
    def __init__(self, message: str) -> None:
        self.message = message
        self.path = ()
        self.absolute_path = ()


def iter_errors(doc) -> list:
    errs = sorted(validator().iter_errors(doc), key=lambda e: list(e.path))
    if not errs and (not isinstance(doc, dict) or "unit_id" not in doc):
        return [_Err("missing unit_id (garbage/empty)")]
    return errs
