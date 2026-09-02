#!/usr/bin/env python3
"""Disk-only validator for command-center/schema/conformance-report.schema.json.

jsonschema 4.10 RefResolver fetches https $ref by default. The catalog shim
points at ast-integrate.invalid, which is not a network host. This module
loads the physical schemas from disk and never opens a socket.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SHIM = "command-center/schema/conformance-report.schema.json"
PROFILES = "platform/schema/artifact-class-profiles.schema.json"
RECEIPT = "platform/schema/receipt.schema.json"
FRAGMENT = "#/$defs/conformance-report"


def _load(rel: str) -> dict[str, Any]:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def validator() -> Draft202012Validator:
    profiles = _load(PROFILES)
    receipt = _load(RECEIPT)
    store = {profiles["$id"]: profiles, receipt["$id"]: receipt}
    schema = {"$ref": profiles["$id"] + FRAGMENT}
    resolver = RefResolver(
        base_uri=profiles["$id"], referrer=profiles, store=store
    )
    return Draft202012Validator(schema, resolver=resolver)


def errors_of(doc: Any) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def payload(doc: dict[str, Any]) -> dict[str, Any]:
    """Domain fields live under report (receipt_core additionalProperties=false)."""
    report = doc.get("report")
    if isinstance(report, dict):
        merged = dict(doc)
        merged.update(report)
        return merged
    return doc


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: schema_local.py <artifact.json> [garbage-check]")
        return 2
    path = Path(args[0])
    if not path.is_file():
        path = REPO / args[0]
    doc = json.loads(path.read_text(encoding="utf-8"))
    errs = errors_of(doc)
    if errs:
        print("FAILED:ARC-0108 schema-invalid")
        for e in errs[:20]:
            print(" ", e)
        return 1
    if len(args) > 1 and args[1] == "garbage-check":
        for garbage in ({}, {"totally": "unrelated"}, {"blob": "x" * 2000}):
            if not errors_of(garbage):
                print("FAILED:ARC-0108 schema accepted garbage")
                return 1
    print(f"schema-valid errors=0 path={path.as_posix()}")
    print("SUCCESS:ARC-0108 schema-local")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
