"""CouncilSpec schema validation and named-preset set-difference coverage."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from presets import NAMED_AT_11200_11225, all_presets, schema_invalid_fixture

HERE = Path(__file__).resolve().parent
SCHEMA_PATH = HERE / "councilspec.schema.json"


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validator() -> Draft202012Validator:
    schema = load_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def error_strings(instance: dict[str, Any]) -> list[str]:
    v = validator()
    return [f"{list(e.path)}: {e.message}" for e in v.iter_errors(instance)]


def validate_all() -> dict[str, Any]:
    specs = all_presets()
    v = validator()
    rows = []
    invalid = []
    for spec in specs:
        errs = [f"{list(e.path)}: {e.message}" for e in v.iter_errors(spec)]
        ok = not errs
        rows.append({"id": spec["id"], "schema_ok": ok, "errors": errs})
        if not ok:
            invalid.append(spec["id"])
    ids = {s["id"] for s in specs}
    named = set(NAMED_AT_11200_11225)
    missing_named = sorted(named - ids)
    extra_named_flag = sorted(
        s["id"]
        for s in specs
        if s["meta"]["named_at_11200_11225"] and s["id"] not in named
    )
    bad = schema_invalid_fixture()
    bad_errs = error_strings(bad)
    return {
        "n_presets": len(specs),
        "n_schema_ok": sum(1 for r in rows if r["schema_ok"]),
        "invalid_ids": invalid,
        "named_required": sorted(named),
        "named_missing": missing_named,
        "named_coverage_ok": not missing_named,
        "unexpected_named_flags": extra_named_flag,
        "negative_control": {
            "id": bad["id"],
            "errors": bad_errs,
            "fired": len(bad_errs) > 0,
        },
        "rows": rows,
    }
