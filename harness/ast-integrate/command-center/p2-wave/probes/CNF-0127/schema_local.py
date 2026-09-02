"""Validate CNF-0127 artifacts against benchmark-report using on-disk $ref only."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema.validators import RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/benchmark-report.schema.json"
BASE = "https://ast-integrate.invalid/"
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"x": "x" * 200},
)

_Validator = getattr(jsonschema, "Draft202012Validator", jsonschema.Draft7Validator)


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


def validator():
    schema_path = REPO / SCHEMA_REL
    schema = _load(schema_path)
    resolver = RefResolver(
        base_uri=str(schema.get("$id") or (BASE + SCHEMA_REL)),
        referrer=schema,
        store=disk_store(),
    )
    return _Validator(schema, resolver=resolver)


def error_list(doc: Any) -> list[str]:
    out: list[str] = []
    for err in sorted(validator().iter_errors(doc), key=lambda e: list(e.path)):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return out


def validate_or_die(doc: Any) -> None:
    errs = error_list(doc)
    if errs:
        print("FAILED:CNF-0127 schema errors")
        for line in errs[:30]:
            print(" ", line)
        raise SystemExit(1)
    for g in GARBAGE:
        if not error_list(g):
            print("FAILED:CNF-0127 schema accepted garbage", list(g)[:2] or "{}")
            raise SystemExit(1)


def domain(doc: dict[str, Any]) -> dict[str, Any]:
    """Domain payload lives under report when receipt_core forbids extra keys."""
    for key in ("report", "extensions"):
        blob = doc.get(key)
        if isinstance(blob, dict) and isinstance(blob.get("cases"), list):
            return blob
    return doc
