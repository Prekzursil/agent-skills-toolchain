"""Offline validator for command-center/schema/coverage-map.schema.json.

The catalog shim $ref targets https://ast-integrate.invalid/... which has no
DNS. jsonschema 4.10 Draft7Validator follows that URL over the network and
raises RefResolutionError. Map those $id values onto files on this worktree
and never open a socket.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import RefResolutionError
from jsonschema.validators import RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/coverage-map.schema.json"
BASE = "https://ast-integrate.invalid/"
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 400},
    {"unit_id": "SYN-0047", "state": "SUCCESS"},
    {"report": {"kind": "coverage-map"}},
)


class OfflineResolver(RefResolver):
    def resolve_remote(self, uri: str):  # noqa: ARG002
        raise RefResolutionError(f"offline: refusing remote fetch {uri!r}")


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def disk_store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    for root in (REPO / "platform" / "schema", REPO / "command-center" / "schema"):
        if not root.is_dir():
            continue
        for path in root.glob("*.json"):
            try:
                doc = _load(path)
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(doc, dict):
                continue
            rel = path.relative_to(REPO).as_posix()
            store[BASE + rel] = doc
            store[path.resolve().as_uri()] = doc
            sid = doc.get("$id")
            if isinstance(sid, str) and sid:
                store[sid] = doc
    return store


def validator(rel: str = SCHEMA_REL) -> Draft202012Validator:
    schema_path = REPO / rel
    schema = _load(schema_path)
    resolver = OfflineResolver(
        base_uri=str(schema.get("$id") or (BASE + rel)),
        referrer=schema,
        store=disk_store(),
    )
    return Draft202012Validator(schema, resolver=resolver)


def error_list(doc: Any, rel: str = SCHEMA_REL) -> list[str]:
    out: list[str] = []
    try:
        for err in sorted(validator(rel).iter_errors(doc), key=lambda e: list(e.path)):
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            out.append(f"{loc}: {err.message}")
    except RefResolutionError as exc:
        out.append(f"<ref>: {exc}")
    return out


def validate_or_die(doc: Any, label: str = "SYN-0047") -> None:
    errs = error_list(doc)
    if errs:
        print(f"FAILED:{label} schema errors")
        for line in errs[:30]:
            print(" ", line)
        raise SystemExit(1)
    for garbage in GARBAGE:
        if not error_list(garbage):
            print(f"FAILED:{label} schema accepted garbage {list(garbage)[:2] or '{}'}")
            raise SystemExit(1)


def payload(doc: dict | None) -> dict:
    """receipt_core forbids extra top-level keys; domain lives under report."""
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
