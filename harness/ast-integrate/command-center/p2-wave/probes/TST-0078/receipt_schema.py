"""Offline test-receipt schema check for TST-0078 probes and emit.

jsonschema 4.10 Draft7Validator has no `registry=` kwarg (that is 4.18+).
Catalog shims $ref https://ast-integrate.invalid/... which RefResolver would
fetch from the network; this module binds those ids to on-disk files.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA = "command-center/schema/test-receipt.schema.json"
BASE = "https://ast-integrate.invalid/"
STORE_RELS = (
    "command-center/schema/test-receipt.schema.json",
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def matrix_of(doc: dict[str, Any]) -> dict[str, Any]:
    matrix = doc.get("matrix")
    if isinstance(matrix, dict) and isinstance(matrix.get("cells"), list):
        return matrix
    report = doc.get("report")
    if isinstance(report, dict):
        inner = report.get("matrix")
        if isinstance(inner, dict) and isinstance(inner.get("cells"), list):
            return inner
    raise KeyError("receipt has no matrix.cells")


def _load(rel: str) -> dict[str, Any]:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def _no_network(uri: str):
    raise jsonschema.exceptions.RefResolutionError(
        f"refusing network schema retrieve: {uri}"
    )


def validator() -> jsonschema.Draft7Validator:
    schema = _load(SCHEMA)
    store: dict[str, dict[str, Any]] = {}
    for rel in STORE_RELS:
        doc = _load(rel)
        store[BASE + rel.replace("\\", "/")] = doc
        ident = doc.get("$id")
        if isinstance(ident, str) and ident:
            store[ident] = doc
    resolver = jsonschema.RefResolver.from_schema(
        schema,
        store=store,
        handlers={"http": _no_network, "https": _no_network},
    )
    return jsonschema.Draft7Validator(schema, resolver=resolver)


def validate_test_receipt(doc: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def assert_receipt(doc: dict[str, Any], label: str) -> int:
    errs = validate_test_receipt(doc)
    if errs:
        print(f"FAILED:{label} schema-invalid")
        for item in errs[:12]:
            print(" ", item)
        return 1
    return 0
