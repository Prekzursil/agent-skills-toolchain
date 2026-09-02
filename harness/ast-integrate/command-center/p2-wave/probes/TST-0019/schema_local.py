"""Offline jsonschema $ref resolution for ast-integrate.invalid (no network)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonschema import Draft7Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
BASE = "https://ast-integrate.invalid/"
SCHEMA_REL = "command-center/schema/detector-control.schema.json"
STORE_FILES = {
    "https://ast-integrate.invalid/command-center/schema/detector-control.schema.json": (
        REPO / SCHEMA_REL
    ),
    "https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json": (
        REPO / "platform/schema/artifact-class-profiles.schema.json"
    ),
    "https://ast-integrate.invalid/platform/schema/receipt.schema.json": (
        REPO / "platform/schema/receipt.schema.json"
    ),
}


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def retrieve(uri: str) -> dict:
    if not uri.startswith(BASE):
        raise ValueError(f"refuses non-estate uri: {uri}")
    rel = uri[len(BASE) :].split("#", 1)[0]
    path = REPO / rel
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def load_store() -> dict:
    store = {}
    for uri, path in STORE_FILES.items():
        store[uri] = json.loads(path.read_text(encoding="utf-8"))
    return store


def load_schema(rel: str = SCHEMA_REL) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def validator(rel: str = SCHEMA_REL) -> Draft7Validator:
    schema = load_schema(rel)
    store = load_store()
    schema_id = str(schema.get("$id") or "")
    if schema_id:
        store[schema_id] = schema
    resolver = RefResolver(
        base_uri=str(schema.get("$id") or BASE),
        referrer=schema,
        store=store,
        handlers={"https": retrieve},
    )
    return Draft7Validator(schema, resolver=resolver)


def iter_errors(doc: dict, rel: str = SCHEMA_REL) -> list:
    return sorted(validator(rel).iter_errors(doc), key=lambda e: list(e.path))


def payload(doc: dict) -> dict:
    """Top-level receipt plus report overlay so probes can read domain fields."""
    if not isinstance(doc, dict):
        return {}
    out = dict(doc)
    report = doc.get("report")
    if isinstance(report, dict):
        out.update(report)
    return out


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    if not path.is_file():
        raise FileNotFoundError(rel)
    sha, size = digest_file(path)
    return {
        "bytes": size,
        "eol": "LF",
        "exists": True,
        "path": rel,
        "role": role,
        "sha256": sha,
    }
