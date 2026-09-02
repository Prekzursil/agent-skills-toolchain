#!/usr/bin/env python3
"""Draft 2020-12 validation with a non-vacuous invalid record.

Catalog output_schema is a generated $ref shim. Following it from this host
raises RefResolutionError (ast-integrate.invalid is not on the network).
The executable contract is the unit-local artifact.schema.json.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/p2-wave/probes/CNL-0110/artifact.schema.json"
CATALOG_SCHEMA_REL = "command-center/schema/council-preset.schema.json"


def _boot_jsonschema():
    cwd = Path.cwd().resolve()
    cleaned = []
    for p in sys.path:
        if not p:
            continue
        try:
            if Path(p).resolve() == cwd:
                continue
        except OSError:
            pass
        cleaned.append(p)
    sys.path[:] = cleaned
    sys.modules.pop("platform", None)
    for name in list(sys.modules):
        if name == "jsonschema" or name.startswith("jsonschema."):
            sys.modules.pop(name, None)
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import SchemaError

    return Draft202012Validator, SchemaError


Draft202012Validator, SchemaError = _boot_jsonschema()


def load_schema() -> dict:
    path = REPO / SCHEMA_REL
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return schema


def validator() -> Draft202012Validator:
    return Draft202012Validator(load_schema())


def error_count(doc: dict) -> int:
    return sum(1 for _ in validator().iter_errors(doc))


def invalid_record(good: dict) -> dict:
    """Deliberately invalid: blend outcome plus dropped required nearest sibling."""
    bad = copy.deepcopy(good)
    bad["answers"]["unreconcilable_pair_outcome"] = "blended-requirement"
    bad["preset"]["delta"]["outcomes"]["unreconcilable_pair"] = "blended-requirement"
    bad.pop("nearest_sibling", None)
    return bad


def validate_pair(good: dict) -> dict:
    try:
        Draft202012Validator.check_schema(load_schema())
        schema_ok = True
        schema_error = None
    except SchemaError as exc:
        schema_ok = False
        schema_error = str(exc)
    good_n = error_count(good)
    bad_n = error_count(invalid_record(good))
    catalog_shim = REPO / CATALOG_SCHEMA_REL
    return {
        "validator": "jsonschema.Draft202012Validator",
        "schema": SCHEMA_REL,
        "catalog_schema_declared": CATALOG_SCHEMA_REL,
        "catalog_schema_present": catalog_shim.is_file(),
        "catalog_schema_note": (
            "Declared catalog schema is a $ref shim to "
            "https://ast-integrate.invalid/... ; probes validate the unit-local "
            "schema so they neither hang on DNS nor accept a vacuous envelope."
        ),
        "schema_ok": schema_ok,
        "schema_error": schema_error,
        "affected_error_count": good_n,
        "invalid_record_error_count": bad_n,
        "vacuous": bad_n == 0,
    }
