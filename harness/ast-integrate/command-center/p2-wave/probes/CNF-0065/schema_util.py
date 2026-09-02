"""Offline catalog-schema validation plus the unit-local claims contract.

The catalog output_schema is a generated $ref shim whose $id lives on
https://ast-integrate.invalid/. jsonschema 4.10 on this host tries to fetch
that URL and raises RefResolutionError. This module maps those $ids onto
the files in-tree and layers a unit-local contract so NOT-REPRODUCIBLE
without a named prerequisite is a schema-red, not only a Python check.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG_SCHEMA = "command-center/schema/benchmark-report.schema.json"
CONTRACT_SCHEMA = HERE / "contract.schema.json"
STORE_RELS = (
    "command-center/schema/benchmark-report.schema.json",
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def _load(rel: str | Path) -> dict:
    path = rel if isinstance(rel, Path) else (REPO / rel)
    return json.loads(path.read_text(encoding="utf-8"))


def catalog_validator() -> jsonschema.Draft7Validator:
    store: dict[str, dict] = {}
    for rel in STORE_RELS:
        data = _load(rel)
        ident = data.get("$id")
        if not isinstance(ident, str) or not ident:
            raise RuntimeError(f"schema {rel} missing $id")
        store[ident] = data
    schema = store["https://ast-integrate.invalid/command-center/schema/benchmark-report.schema.json"]
    resolver = jsonschema.RefResolver(
        base_uri=schema["$id"],
        referrer=schema,
        store=store,
    )
    return jsonschema.Draft7Validator(schema, resolver=resolver)


def contract_validator() -> jsonschema.Draft7Validator:
    schema = _load(CONTRACT_SCHEMA)
    jsonschema.Draft7Validator.check_schema(schema)
    return jsonschema.Draft7Validator(schema)


def error_messages(doc: object) -> list[str]:
    out: list[str] = []
    try:
        for err in catalog_validator().iter_errors(doc):
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            out.append(f"catalog:{loc}: {err.message}")
    except jsonschema.RefResolutionError as exc:
        out.append(f"catalog:ref-resolution:{exc}")
    try:
        for err in contract_validator().iter_errors(doc):
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            out.append(f"contract:{loc}: {err.message}")
    except jsonschema.RefResolutionError as exc:
        out.append(f"contract:ref-resolution:{exc}")
    return out


def report_block(doc: dict) -> dict:
    block = doc.get("report")
    return block if isinstance(block, dict) else {}


def claims(doc: dict) -> list:
    rows = report_block(doc).get("claims")
    if not isinstance(rows, list):
        rows = doc.get("claims")
    return rows if isinstance(rows, list) else []


def sampling(doc: dict) -> dict:
    block = report_block(doc).get("sampling")
    if not isinstance(block, dict):
        block = doc.get("sampling")
    return block if isinstance(block, dict) else {}


def noise_floor(doc: dict) -> dict:
    block = report_block(doc).get("noise_floor")
    if not isinstance(block, dict):
        block = doc.get("noise_floor")
    return block if isinstance(block, dict) else {}
