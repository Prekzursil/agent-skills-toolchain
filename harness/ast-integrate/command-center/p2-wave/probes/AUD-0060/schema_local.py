#!/usr/bin/env python3
"""Offline validator for the catalog audit-metric-baseline shim.

jsonschema 4.10 on this worker follows $id/$ref over HTTPS to
https://ast-integrate.invalid/ which is not a host. Load the physical
files from disk into a RefResolver store so garbage is rejected and a
well-formed receipt can validate with no network.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/audit-metric-baseline.schema.json"
BASE_URI = "https://ast-integrate.invalid/"
STORE_RELS = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\n{command}".encode("utf-8")).hexdigest()


def load_schema() -> dict[str, Any]:
    return json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))


def _store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for rel in STORE_RELS:
        doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
        store[BASE_URI + rel] = doc
        ident = doc.get("$id")
        if isinstance(ident, str) and ident:
            store[ident] = doc
    return store


def validator() -> Draft202012Validator:
    schema = load_schema()
    resolver = RefResolver(
        base_uri=str(schema.get("$id") or (BASE_URI + SCHEMA_REL)),
        referrer=schema,
        store=_store(),
    )
    return Draft202012Validator(schema, resolver=resolver)


def iter_errors(doc: object) -> list:
    return sorted(validator().iter_errors(doc), key=lambda e: list(e.path))


def errors_for(doc: object) -> list[str]:
    out: list[str] = []
    for err in iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return out


def garbage_accepted() -> object | None:
    v = validator()
    for garbage in (
        {},
        {"unit_id": "AUD-0060", "state": "SUCCESS"},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if v.is_valid(garbage):
            return garbage
    return None


def err_fp(errs: list[str]) -> str:
    blob = "\n".join(sorted(errs)).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


if __name__ == "__main__":
    bad = garbage_accepted()
    if bad is not None:
        print("FAILED:AUD-0060 schema accepted garbage")
        raise SystemExit(1)
    print("schema_local garbage-rejected")
    print("SUCCESS:AUD-0060-schema-local")
