#!/usr/bin/env python3
"""Offline validator for command-center/schema/citation-audit.schema.json.

The catalog shim $ref's https://ast-integrate.invalid/... which is not a
network host. Resolve those $id values from files on this worktree.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolver
from jsonschema.exceptions import RefResolutionError

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/citation-audit.schema.json"
PHYSICAL = (
    "command-center/schema/citation-audit.schema.json",
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


class OfflineResolver(RefResolver):
    def resolve_remote(self, uri: str):  # noqa: ARG002
        raise RefResolutionError(f"offline: refusing remote fetch {uri!r}")


def load_json(rel: str) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def validator() -> Draft202012Validator:
    shim = load_json(SCHEMA_REL)
    store: dict[str, dict] = {}
    for rel in PHYSICAL:
        doc = load_json(rel)
        sid = doc.get("$id")
        if isinstance(sid, str) and sid:
            store[sid] = doc
    resolver = OfflineResolver(
        base_uri=str(shim.get("$id") or SCHEMA_REL),
        referrer=shim,
        store=store,
    )
    return Draft202012Validator(shim, resolver=resolver)


def errors(doc) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def refuse_garbage() -> int:
    v = validator()
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 200},
        {"unit_id": "CNF-0073", "state": "SUCCESS"},
        {"report": {"kind": "citation-audit"}},
    ):
        if not list(v.iter_errors(garbage)):
            print(f"FAILED:CNF-0073 schema accepted garbage {list(garbage)[:2]}")
            return 1
    return 0


def main() -> int:
    if refuse_garbage() != 0:
        return 1
    art = REPO / "command-center/confirmation/CNF-0073-multilingual-recheck.json"
    if not art.is_file():
        print("FAILED:CNF-0073-schema artifact missing")
        return 1
    doc = json.loads(art.read_text(encoding="utf-8"))
    errs = errors(doc)
    if errs:
        print("FAILED:CNF-0073-schema")
        for e in errs[:20]:
            print(" ", e)
        return 1
    print("SUCCESS:CNF-0073-schema offline citation-audit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
