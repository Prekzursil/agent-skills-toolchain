"""Offline audit-finding schema check (disk $ref store, no network)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.validators import RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/audit-finding.schema.json"
BASE = "https://ast-integrate.invalid/"
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {"unit_id": "AUD-0052", "state": "SUCCESS", "sentinel": "SUCCESS:AUD-0052"},
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def disk_store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    roots = [
        REPO / "platform" / "schema",
        REPO / "command-center" / "schema",
    ]
    for root in roots:
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


def validator() -> Draft202012Validator:
    schema_path = REPO / SCHEMA_REL
    schema = _load(schema_path)
    resolver = RefResolver(
        base_uri=str(schema.get("$id") or (BASE + SCHEMA_REL)),
        referrer=schema,
        store=disk_store(),
    )
    return Draft202012Validator(schema, resolver=resolver)


def error_list(doc: Any) -> list[str]:
    out: list[str] = []
    try:
        errs = list(validator().iter_errors(doc))
    except Exception as exc:
        return [f"resolver:{type(exc).__name__}: {exc}"]
    for err in sorted(errs, key=lambda e: list(e.path)):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return out


def garbage_is_rejected() -> bool:
    return all(bool(error_list(g)) for g in GARBAGE)
