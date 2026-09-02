"""Phase-7A CouncilSpec acceptor — schema only, no deliberation.

The acceptor validates a composed CouncilSpec against the bundled Phase-7A
envelope schema (``schema/councilspec.7a.envelope.json``). When a live
IMP-0261 CouncilSpec schema exists in the tree it is applied as well and the
report says so (``live_schema``). The acceptor never runs a round.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .compose import SECTIONS

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
ENVELOPE_SCHEMA_PATH = HERE / "schema" / "councilspec.7a.envelope.json"
RUNTIME_ID = "phase-7a-envelope-acceptor"


def _rel(path: Path) -> str:
    try:
        return path.relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix()


def envelope_schema_path() -> Path:
    """Path of the bundled Phase-7A envelope schema."""
    return ENVELOPE_SCHEMA_PATH


def live_7a_schema_path() -> Path | None:
    """Path of a live IMP-0261 CouncilSpec schema if one has landed, else None."""
    cand = REPO / "command-center" / "schema" / "councilspec.schema.json"
    return cand if cand.is_file() else None


def load_envelope_schema() -> dict[str, Any]:
    return json.loads(ENVELOPE_SCHEMA_PATH.read_text(encoding="utf-8"))


def _type_ok(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    return True


def structural_errors(value: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    """Stdlib check of the subset of draft-07 the envelope schema uses.

    Handles ``type``, ``required``, ``properties``, ``additionalProperties``,
    ``items``, ``minItems``, ``minLength``, ``minimum`` and ``const``.
    """
    errors: list[str] = []
    expected = schema.get("type")
    if expected is not None and not _type_ok(value, expected):
        return [f"{path}: expected {expected}"]
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: must equal {schema['const']!r}")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}: missing:{key}")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in props:
                    errors.append(f"{path}: extra:{key}")
        for key, sub in props.items():
            if key in value:
                errors.extend(structural_errors(value[key], sub, f"{path}.{key}"))
    if isinstance(value, list):
        if len(value) < int(schema.get("minItems", 0)):
            errors.append(f"{path}: fewer than {schema['minItems']} items")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for i, item in enumerate(value):
                errors.extend(structural_errors(item, item_schema, f"{path}[{i}]"))
    if isinstance(value, str) and len(value) < int(schema.get("minLength", 0)):
        errors.append(f"{path}: shorter than {schema['minLength']}")
    if isinstance(value, (int, float)) and not isinstance(value, bool) and "minimum" in schema:
        if value < schema["minimum"]:
            errors.append(f"{path}: below minimum {schema['minimum']}")
    return errors


def _jsonschema_errors(schema: dict[str, Any], spec: dict[str, Any]) -> list[str] | None:
    """Errors from the ``jsonschema`` package when it is installed, else None."""
    try:
        import jsonschema  # type: ignore
    except Exception:
        return None
    validator = jsonschema.Draft7Validator(schema)
    return [e.message for e in validator.iter_errors(spec)]


def validate_councilspec(spec: dict[str, Any]) -> dict[str, Any]:
    """Validate ``spec`` against the envelope (and live schema when present)."""
    envelope = ENVELOPE_SCHEMA_PATH
    live = live_7a_schema_path()
    base = {
        "runtime": RUNTIME_ID,
        "schema": _rel(envelope),
        "schema_path": _rel(envelope),
        "live_schema": live is not None,
        "live_schema_path": None if live is None else _rel(live),
    }
    if not isinstance(spec, dict):
        return {"ok": False, "errors": ["$: not an object"], **base}
    errors: list[str] = []
    errors.extend(f"missing:{k}" for k in SECTIONS if k not in spec)
    errors.extend(f"extra:{k}" for k in spec if k not in SECTIONS)
    schema = load_envelope_schema()
    errors.extend(structural_errors(spec, schema))
    extra = _jsonschema_errors(schema, spec)
    if extra:
        errors.extend(f"jsonschema:{msg}" for msg in extra)
    if live is not None:
        try:
            live_body = json.loads(live.read_text(encoding="utf-8"))
            live_errors = _jsonschema_errors(live_body, spec)
            if live_errors is None:
                live_errors = structural_errors(spec, live_body)
            errors.extend(f"live:{msg}" for msg in live_errors)
        except Exception as exc:  # unreadable live schema is a validation failure, not a pass
            errors.append(f"live-schema:{exc}")
    deduped = list(dict.fromkeys(errors))
    return {"ok": not deduped, "errors": deduped, **base}
