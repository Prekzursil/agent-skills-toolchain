"""On-disk $ref resolution for command-center/schema/stopping-verdict.schema.json.

The catalog schema is a generated shim whose $ref targets
https://ast-integrate.invalid/... — never fetch that host.
"""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/stopping-verdict.schema.json"
STORE_RELS = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)
GARBAGE = (
    {},
    {"totally": "unrelated", "overall_verdict": "PROGRAM-COMPLETE"},
    {"blob": "x" * 2000},
)


def disk_store() -> dict:
    store: dict = {}
    for rel in STORE_RELS:
        data = json.loads((REPO / rel).read_text(encoding="utf-8"))
        sid = data.get("$id")
        if isinstance(sid, str) and sid:
            store[sid] = data
        store["https://ast-integrate.invalid/" + rel] = data
    return store


def validator(declared: str = SCHEMA_REL) -> Draft202012Validator:
    schema = json.loads((REPO / declared).read_text(encoding="utf-8"))
    resolver = RefResolver(
        base_uri=str(
            schema.get("$id") or ("https://ast-integrate.invalid/" + declared)
        ),
        referrer=schema,
        store=disk_store(),
    )
    return Draft202012Validator(schema, resolver=resolver)


def iter_errors(doc: object, declared: str = SCHEMA_REL) -> list[str]:
    out: list[str] = []
    for err in validator(declared).iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def assert_rejects_garbage(declared: str = SCHEMA_REL) -> None:
    for g in GARBAGE:
        if not iter_errors(g, declared):
            raise SystemExit(f"FAILED:SYN-0043 schema accepted garbage {list(g)[:2]}")
