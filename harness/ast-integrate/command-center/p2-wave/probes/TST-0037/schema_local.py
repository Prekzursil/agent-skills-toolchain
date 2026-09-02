"""Disk-only validator for command-center/schema/conformance-report.schema.json.

The catalog file is a generated $ref shim to https://ast-integrate.invalid/...
which has no DNS. jsonschema on this box follows that URL and raises
RefResolutionError (or, if the hop is skipped, accepts garbage). This module
maps the prefix onto files under the repo root and never opens a socket.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PREFIX = "https://ast-integrate.invalid/"
SCHEMA_REL = "command-center/schema/conformance-report.schema.json"
SHIM_URI = PREFIX + SCHEMA_REL
STORE_FILES = {
    SHIM_URI: REPO / SCHEMA_REL,
    PREFIX + "platform/schema/artifact-class-profiles.schema.json": (
        REPO / "platform/schema/artifact-class-profiles.schema.json"
    ),
    PREFIX + "platform/schema/receipt.schema.json": (
        REPO / "platform/schema/receipt.schema.json"
    ),
}


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load_store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for uri, path in STORE_FILES.items():
        doc = json.loads(path.read_text(encoding="utf-8"))
        store[uri] = doc
        rid = str(doc.get("$id") or "")
        if rid:
            store[rid] = doc
    return store


def _disk_handler(uri: str) -> Any:
    if not uri.startswith(PREFIX):
        raise ValueError(f"refusing non-local schema uri: {uri}")
    rel = uri[len(PREFIX) :].split("#", 1)[0]
    path = (REPO / rel).resolve()
    root = REPO.resolve()
    if not str(path).startswith(str(root) + "/"):
        raise ValueError(f"schema uri escapes repo: {uri}")
    if not path.is_file():
        raise FileNotFoundError(rel)
    return json.loads(path.read_text(encoding="utf-8"))


def validator() -> Draft202012Validator:
    store = load_store()
    schema = store[SHIM_URI]
    resolver = RefResolver(
        base_uri=SHIM_URI,
        referrer=schema,
        store=store,
        handlers={"https": _disk_handler, "http": _disk_handler},
        cache_remote=False,
    )
    return Draft202012Validator(schema, resolver=resolver)


def iter_errors(doc: Any) -> list:
    return sorted(validator().iter_errors(doc), key=lambda e: list(e.path))


def error_messages(doc: Any) -> list[str]:
    out: list[str] = []
    for err in iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return out


def payload(doc: Any) -> dict:
    """Overlay report fields so probes can read domain payload from either shape."""
    if not isinstance(doc, dict):
        return {}
    out = dict(doc)
    report = doc.get("report")
    if isinstance(report, dict):
        for key, value in report.items():
            out.setdefault(key, value)
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


def garbage_rejected() -> None:
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"x": "x" * 200},
        {"blob": "x" * 2000},
        {"unit_id": "TST-0037", "state": "SUCCESS"},
    ):
        if not iter_errors(garbage):
            raise AssertionError(f"schema accepted garbage keys={list(garbage)[:6]}")
