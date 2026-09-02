"""Validate CNF-0091 against council-audit using on-disk $ref only.

jsonschema 4.10.3 Draft7Validator follows https://ast-integrate.invalid
over the network. This store maps those $ids onto files under the repo.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.validators import RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/council-audit.schema.json"
BASE = "https://ast-integrate.invalid/"
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {"unit_id": "CNF-0091", "state": "SUCCESS"},
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
    for err in sorted(validator().iter_errors(doc), key=lambda e: list(e.path)):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return out


def validate_or_die(doc: Any, label: str = "CNF-0091") -> None:
    errs = error_list(doc)
    if errs:
        print(f"FAILED:{label} schema errors")
        for line in errs[:30]:
            print(" ", line)
        raise SystemExit(1)
    for g in GARBAGE:
        if not error_list(g):
            print(f"FAILED:{label} schema accepted garbage", list(g)[:2])
            raise SystemExit(1)


def audit_payload(doc: dict[str, Any]) -> dict[str, Any]:
    """Domain fields live under report (receipt_core additionalProperties:false)."""
    rep = doc.get("report")
    if isinstance(rep, dict):
        return rep
    return doc
