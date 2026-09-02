"""Disk-only validator for the research-registry shim.

jsonschema 4.10 follows https://ast-integrate.invalid $ref over the network.
Map those $ids onto files already in this worktree. Never fetch. Never rebuild
the generated schema (no ADV circle).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/research-registry.schema.json"
SCHEMA_PATH = REPO / SCHEMA_REL

STORE_RELS = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def schema_store() -> dict[str, dict]:
    store: dict[str, dict] = {}
    for rel in STORE_RELS:
        path = REPO / rel
        if not path.is_file():
            raise SystemExit(f"FAILED:RES-0127 schema file missing {rel}")
        doc = json.loads(path.read_text(encoding="utf-8"))
        sid = doc.get("$id")
        if not isinstance(sid, str) or not sid:
            raise SystemExit(f"FAILED:RES-0127 schema {rel} has no $id")
        store[sid] = doc
    return store


def validator():
    shim = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    resolver = RefResolver.from_schema(shim, store=schema_store())
    return Draft202012Validator(shim, resolver=resolver)


def error_list(instance: object) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(instance):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def error_fingerprint(errs: list[str]) -> str:
    body = "\n".join(errs).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def registry_of(doc: dict) -> dict:
    """Prefer report.registry (receipt_core); fall back to a top-level copy."""
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    reg = report.get("registry")
    if isinstance(reg, dict):
        return reg
    top = doc.get("registry")
    return top if isinstance(top, dict) else {}


def three_way_of(doc: dict) -> dict:
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    three = report.get("three_way_partition_with_hashes")
    if isinstance(three, dict):
        return three
    top = doc.get("three_way_partition_with_hashes")
    return top if isinstance(top, dict) else {}
