"""Phase-7A CouncilSpec acceptor — schema only, no deliberation."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .compose import SECTIONS

REPO = Path(__file__).resolve().parents[4]


def live_7a_schema_path() -> Path | None:
    cand = REPO / "command-center" / "schema" / "councilspec.schema.json"
    return cand if cand.is_file() else None


def validate_councilspec(spec: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(spec, dict):
        return {"ok": False, "errors": ["not an object"]}
    missing = [k for k in SECTIONS if k not in spec]
    extra = [k for k in spec if k not in SECTIONS]
    errors = [f"missing:{k}" for k in missing] + [f"extra:{k}" for k in extra]
    schema = live_7a_schema_path()
    if schema is not None:
        try:
            import json
            import jsonschema

            body = json.loads(schema.read_text(encoding="utf-8"))
            v = jsonschema.Draft7Validator(body)
            errors.extend(e.message for e in v.iter_errors(spec))
        except Exception as exc:
            errors.append(f"schema:{exc}")
    return {
        "ok": not errors,
        "errors": errors,
        "schema": str(schema) if schema else None,
        "schema_path": str(schema) if schema else None,
    }
