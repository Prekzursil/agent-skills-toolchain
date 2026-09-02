#!/usr/bin/env python3
"""Shared jsonschema helpers for IMP-0433 probes. No platform/schema_resolver."""
from __future__ import annotations

import copy
import json
from pathlib import Path

try:
    import jsonschema
    from jsonschema import Draft7Validator
except ImportError as exc:  # pragma: no cover
    raise SystemExit(f"FAILED:IMP-0433 jsonschema missing: {exc}") from exc

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/receipt.schema.json"
SCHEMA_PATH = REPO / SCHEMA_REL
FIXDIR = REPO / "command-center/p2-wave/fixtures/IMP-0433"
SENTINEL = "SENTINEL:IMP-0433:RECEIPT-SCHEMA-AUTHORED"
GARBAGE = (
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {},
)
KNOWN_BAD_SCHEMA = {"type": 123, "required": "not-an-array"}


def load_schema() -> dict:
    if not SCHEMA_PATH.is_file() or SCHEMA_PATH.stat().st_size <= 0:
        raise SystemExit(f"FAILED:IMP-0433 schema absent: {SCHEMA_REL}")
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validator(schema: dict | None = None) -> Draft7Validator:
    return Draft7Validator(schema if schema is not None else load_schema())


def error_messages(doc: dict, schema: dict | None = None) -> list[str]:
    errs = sorted(validator(schema).iter_errors(doc), key=lambda e: list(e.path))
    out = []
    for e in errs:
        path = ".".join(str(p) for p in e.path) or "<root>"
        out.append(f"{path}: {e.message}")
    return out


def is_valid(doc: dict, schema: dict | None = None) -> bool:
    return not error_messages(doc, schema)


def load_fixture(name: str) -> dict:
    path = FIXDIR / name
    return json.loads(path.read_text(encoding="utf-8"))


def check_schema_ok(schema: dict) -> tuple[bool, str]:
    try:
        Draft7Validator.check_schema(schema)
        return True, ""
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


def check_schema_fails(doc: dict) -> bool:
    try:
        Draft7Validator.check_schema(doc)
        return False
    except Exception:
        return True


def as_blocked(base: dict) -> dict:
    d = copy.deepcopy(base)
    d["state"] = "BLOCKED"
    d["failure"] = {
        "classification": ["fixture"],
        "reason": "blocked copy for named-strictness counter-measurement",
    }
    return d
