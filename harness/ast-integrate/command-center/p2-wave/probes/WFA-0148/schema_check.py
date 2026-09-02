#!/usr/bin/env python3
"""Disk-only classifier-audit validation. Never fetch ast-integrate.invalid."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/foundry-artifact.schema.json"
SCHEMA_DECL = SCHEMA_REL + "#/$defs/classifier-audit"
STORE_FILES = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
)


def load_store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for rel in STORE_FILES:
        path = REPO / rel
        if not path.is_file():
            raise FileNotFoundError(rel)
        doc = json.loads(path.read_text(encoding="utf-8"))
        store["https://ast-integrate.invalid/" + rel] = doc
        store[path.resolve().as_uri()] = doc
        sid = doc.get("$id")
        if isinstance(sid, str) and sid:
            store[sid] = doc
    return store


def validator() -> Draft202012Validator:
    lib = REPO / "platform" / "lib"
    if str(lib) not in sys.path:
        sys.path.insert(0, str(lib))
    try:
        from schema_resolver import validator_for  # noqa: WPS433

        return validator_for(SCHEMA_DECL)
    except Exception:
        pass
    store = load_store()
    profiles_rel = "platform/schema/artifact-class-profiles.schema.json"
    profiles = json.loads((REPO / profiles_rel).read_text(encoding="utf-8"))
    base = str(profiles.get("$id") or (REPO / profiles_rel).resolve().as_uri())
    frag = base + "#/$defs/classifier-audit"
    resolver = RefResolver(base_uri=base, referrer=profiles, store=store)
    return Draft202012Validator({"$ref": frag}, resolver=resolver)


def error_list(doc: object) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def assert_rejects_garbage() -> list[str]:
    sample: list[str] = []
    for blob in GARBAGE:
        errs = error_list(blob)
        if not errs:
            raise ValueError(f"schema accepted garbage {list(blob)[:3]}")
        sample.append(errs[0])
    return sample


def payload_of(doc: dict[str, Any]) -> dict[str, Any]:
    """Domain fields live under report; probes accept either layout."""
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    merged: dict[str, Any] = dict(report)
    for key, value in doc.items():
        if key != "report":
            merged[key] = value
    return merged


def validate_or_die(doc: object) -> list[str]:
    garbage = assert_rejects_garbage()
    errs = error_list(doc)
    if errs:
        print("FAILED:WFA-0148 schema-invalid")
        for line in errs[:24]:
            print(" ", line)
        raise SystemExit(1)
    return garbage


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: schema_check.py <artifact.json>")
        raise SystemExit(2)
    path = Path(sys.argv[1])
    doc = json.loads(path.read_text(encoding="utf-8"))
    validate_or_die(doc)
    print("SUCCESS:WFA-0148-schema-valid")
