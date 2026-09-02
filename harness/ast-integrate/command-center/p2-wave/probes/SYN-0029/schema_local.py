#!/usr/bin/env python3
"""Offline jsonschema $ref resolution for requirement-closure (no network).

jsonschema 4.10 follows https://ast-integrate.invalid/... onto the wire and
raises RefResolutionError. Map that prefix onto files under the repo root.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
BASE = "https://ast-integrate.invalid/"
SCHEMA_REL = "command-center/schema/requirement-closure.schema.json"
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"x": "x" * 200},
    {"state": "SUCCESS", "unit_id": "SYN-0029", "report": {"kind": "audit-finding"}},
)


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def retrieve(uri: str) -> dict:
    if uri.startswith("https://json-schema.org/"):
        raise ValueError(f"meta-schema not in disk store: {uri}")
    if not uri.startswith(BASE):
        raise ValueError(f"refuses non-estate uri: {uri}")
    rel = uri[len(BASE) :].split("#", 1)[0]
    path = (REPO / rel).resolve()
    root = REPO.resolve()
    if not str(path).startswith(str(root) + "/"):
        raise ValueError(f"schema uri escapes repo: {uri}")
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def disk_store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for root in (REPO / "platform" / "schema", REPO / "command-center" / "schema"):
        if not root.is_dir():
            continue
        for path in root.glob("*.json"):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(doc, dict):
                continue
            rel = path.relative_to(REPO).as_posix()
            store[BASE + rel] = doc
            sid = doc.get("$id")
            if isinstance(sid, str) and sid:
                store[sid] = doc
    return store


def validator(rel: str = SCHEMA_REL) -> Draft7Validator:
    schema = json.loads((REPO / rel).read_text(encoding="utf-8"))
    resolver = RefResolver(
        base_uri=str(schema.get("$id") or (BASE + rel)),
        referrer=schema,
        store=disk_store(),
        handlers={"https": retrieve, "http": retrieve},
    )
    return Draft7Validator(schema, resolver=resolver)


def error_list(doc: Any, rel: str = SCHEMA_REL) -> list[str]:
    out: list[str] = []
    for err in sorted(validator(rel).iter_errors(doc), key=lambda e: list(e.path)):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return out


def rejects_garbage(rel: str = SCHEMA_REL) -> bool:
    return all(bool(error_list(g, rel)) for g in GARBAGE)


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
    sha, size = digest_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }
