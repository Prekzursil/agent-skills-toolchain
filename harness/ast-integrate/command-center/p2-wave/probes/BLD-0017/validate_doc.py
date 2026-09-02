"""Validate BLD-0017 receipts against the unit-local overlay schema.

The catalog shim at command-center/schema/owner-question-closure.schema.json
$ref's https://ast-integrate.invalid/... . jsonschema 4.10.3 on this host
tries the network and raises RefResolutionError, which the probes must not
treat as a pass and cannot catch as ValidationError. This overlay is the
gate the named probes actually run.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import jsonschema

HERE = Path(__file__).resolve().parent
LOCAL_SCHEMA = HERE / "local_schema.json"
CATALOG_SHIM = (
    HERE.parents[3] / "command-center/schema/owner-question-closure.schema.json"
)


def load_local_schema() -> dict[str, Any]:
    return json.loads(LOCAL_SCHEMA.read_text(encoding="utf-8"))


def validate_doc(doc: dict[str, Any]) -> None:
    jsonschema.Draft7Validator(load_local_schema()).validate(doc)


def mutant_missing_closure_table_is_red(doc: dict[str, Any]) -> bool:
    mutant = copy.deepcopy(doc)
    mutant.pop("closure_table", None)
    report = mutant.get("report")
    if isinstance(report, dict):
        report.pop("closure_table", None)
    try:
        jsonschema.Draft7Validator(load_local_schema()).validate(mutant)
    except jsonschema.ValidationError:
        return True
    return False


def catalog_shim_present() -> bool:
    return CATALOG_SHIM.is_file() and CATALOG_SHIM.stat().st_size > 0
