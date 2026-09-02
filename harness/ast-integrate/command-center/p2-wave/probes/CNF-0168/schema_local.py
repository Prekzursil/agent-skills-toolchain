#!/usr/bin/env python3
"""Disk-only program-gate-report validator for jsonschema 4.10.

platform/lib/schema_resolver.validator_for() passes registry= which
jsonschema 4.10.3 does not accept. Draft7Validator on the catalog shim
fetches https://ast-integrate.invalid over the network. This module
loads the two physical schema files from disk into a RefResolver store
and never leaves the filesystem.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
RECEIPT = REPO / "platform/schema/receipt.schema.json"
PROFILES = REPO / "platform/schema/artifact-class-profiles.schema.json"
SCHEMA_DECL = "command-center/schema/program-gate-report.schema.json"


def validator() -> Draft202012Validator:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    profiles = json.loads(PROFILES.read_text(encoding="utf-8"))
    store = {
        str(receipt["$id"]): receipt,
        str(profiles["$id"]): profiles,
    }
    uri = str(profiles["$id"]) + "#/$defs/program-gate-report"
    schema = {"$ref": uri}
    resolver = RefResolver(base_uri=str(profiles["$id"]) + "/", referrer=schema, store=store)
    return Draft202012Validator(schema, resolver=resolver)


def iter_errors(doc: Any) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


if __name__ == "__main__":
    import sys

    target = REPO / "command-center/receipts/CNF-0168.json"
    if len(sys.argv) > 1:
        target = Path(sys.argv[1])
        if not target.is_absolute():
            target = REPO / target
    doc = json.loads(target.read_text(encoding="utf-8"))
    errs = iter_errors(doc)
    for e in errs:
        print(e)
    if errs:
        print(f"FAILED:schema-invalid errors={len(errs)}")
        raise SystemExit(1)
    print("SUCCESS:schema-valid")
    raise SystemExit(0)
