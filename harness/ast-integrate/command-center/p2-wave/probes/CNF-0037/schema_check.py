"""Validate CNF-0037 against conformance-report using on-disk $ref only."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.validators import RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/conformance-report.schema.json"
BASE = "https://ast-integrate.invalid/"
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {"unit_id": "CNF-0037", "state": "SUCCESS", "sentinel": "SUCCESS:CNF-0037"},
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


def validate_or_die(doc: Any) -> None:
    errs = error_list(doc)
    if errs:
        print("FAILED:CNF-0037 schema errors")
        for line in errs[:30]:
            print(" ", line)
        raise SystemExit(1)
    for g in GARBAGE:
        if not error_list(g):
            print("FAILED:CNF-0037 schema accepted garbage", list(g)[:2])
            raise SystemExit(1)


def report_view(doc: dict[str, Any]) -> dict[str, Any]:
    """Domain payload lives under report when the receipt uses additionalProperties:false."""
    rep = doc.get("report")
    return rep if isinstance(rep, dict) else doc
