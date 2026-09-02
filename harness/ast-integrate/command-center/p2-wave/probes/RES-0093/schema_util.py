"""Local Draft-07 validator for RES-0093.

Catalog command-center/schema/research-registry.schema.json is a generated
shim whose $ref is https://ast-integrate.invalid/... . jsonschema 4.10.3
RefResolver tries the network (measured: RefResolutionError / gaierror).
G-1 does not require that hop. This module validates the per-unit schema.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
from jsonschema.exceptions import ValidationError

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LOCAL_REL = "command-center/p2-wave/probes/RES-0093/benchmark-register.schema.json"
CATALOG_REL = "command-center/schema/research-registry.schema.json"
GARBAGE = [
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"x": "x" * 2000},
]


def load_local() -> dict:
    return json.loads((REPO / LOCAL_REL).read_text(encoding="utf-8"))


def validator() -> jsonschema.Draft7Validator:
    return jsonschema.Draft7Validator(load_local())


def error_list(doc: object) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def validate(doc: object) -> None:
    jsonschema.validate(doc, load_local(), cls=jsonschema.Draft7Validator)


def rejects_garbage() -> bool:
    v = validator()
    return all(list(v.iter_errors(g)) for g in GARBAGE)


__all__ = [
    "CATALOG_REL",
    "GARBAGE",
    "LOCAL_REL",
    "ValidationError",
    "error_list",
    "load_local",
    "rejects_garbage",
    "validate",
    "validator",
]
