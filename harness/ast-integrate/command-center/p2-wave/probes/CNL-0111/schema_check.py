"""Draft 2020-12 validation over affected preset records."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG_SCHEMA_REL = "command-center/schema/council-preset.schema.json"
LOCAL_SCHEMA_REL = (
    "command-center/p2-wave/probes/CNL-0111/council-preset.schema.json"
)


def load_schema() -> dict[str, Any]:
    """Prefer catalog $defs.preset; else the unit-local executable contract.

    The catalog path is a generated shim ($ref to generic_report) with no
    $defs.preset. CNL-0111 does not overwrite that shared file.
    """
    catalog = json.loads((REPO / CATALOG_SCHEMA_REL).read_text(encoding="utf-8"))
    defs = catalog.get("$defs") if isinstance(catalog, dict) else None
    if isinstance(defs, dict) and "preset" in defs:
        catalog["_cnl0111_schema_rel"] = CATALOG_SCHEMA_REL
        return catalog
    local = json.loads((REPO / LOCAL_SCHEMA_REL).read_text(encoding="utf-8"))
    local["_cnl0111_schema_rel"] = LOCAL_SCHEMA_REL
    return local


def preset_schema(schema: dict[str, Any] | None = None) -> dict[str, Any]:
    schema = schema or load_schema()
    defs = schema.get("$defs") or {}
    if "preset" not in defs:
        raise KeyError(
            "no $defs.preset in executable schema "
            f"{schema.get('_cnl0111_schema_rel')}"
        )
    body = dict(defs["preset"])
    body["$schema"] = schema.get("$schema")
    body["$defs"] = defs
    return body


def error_count(validator: Draft202012Validator, doc: Any) -> int:
    return sum(1 for _ in validator.iter_errors(doc))


def validate_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    schema = load_schema()
    schema_rel = schema.pop("_cnl0111_schema_rel", LOCAL_SCHEMA_REL)
    Draft202012Validator.check_schema(schema)
    p_schema = preset_schema(schema)
    p_val = Draft202012Validator(p_schema)
    per: list[dict[str, Any]] = []
    total = 0
    for rec in records:
        n = error_count(p_val, rec)
        total += n
        per.append({"id": rec.get("id"), "errors": n})
    invalid = {"id": "C-INVALID", "name": "vacuity-probe"}
    invalid_errors = error_count(p_val, invalid)
    return {
        "schema": schema_rel,
        "catalog_schema": CATALOG_SCHEMA_REL,
        "validator": "jsonschema.Draft202012Validator",
        "schema_ok": True,
        "record_error_count": total,
        "per_record": per,
        "invalid_record": invalid,
        "invalid_error_count": invalid_errors,
        "vacuous": invalid_errors == 0,
    }
