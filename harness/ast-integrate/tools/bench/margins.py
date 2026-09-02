"""B07 metric inventory and non-inferiority margin table (TST-0301).

The release gate reads a fixed set of metrics (``gate: true`` rows of
``command-center/bench/METRIC-INVENTORY.json``).  Every one of them must carry a
per-metric margin in ``command-center/bench/B07-MARGIN-TABLE.json`` that was
decided *before* any comparison ran.  This module loads both documents,
validates them against their JSON schemas (a self-contained validator: the
measurement harness runs with ``python3 -s`` and no third-party packages) and
reports coverage gaps.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from tools.bench import paths

__all__ = [
    "MarginCoverageError",
    "SchemaError",
    "assert_table_covers_gate",
    "coverage_gaps",
    "gate_metric_ids",
    "load_inventory",
    "load_json",
    "load_margin_table",
    "load_schema",
    "schema_errors",
    "table_by_id",
    "validate_document",
]


class SchemaError(ValueError):
    """A document does not satisfy its JSON schema."""


class MarginCoverageError(ValueError):
    """The margin table does not cover every metric the release gate reads."""


# --------------------------------------------------------------------------- schema
_TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


def _type_ok(value: Any, expected: Any) -> bool:
    names = expected if isinstance(expected, list) else [expected]
    return any(_TYPES.get(name, lambda _v: False)(value) for name in names)


def schema_errors(doc: Any, schema: dict, path: str = "$") -> list[str]:
    """Validate ``doc`` against the draft-2020-12 subset these schemas use.

    Supported keywords: type, const, enum, pattern, minLength, minimum, required,
    properties, additionalProperties, items, minItems.  Returns a list of
    human-readable violations; an empty list means the document validates.
    """
    errors: list[str] = []
    if "type" in schema and not _type_ok(doc, schema["type"]):
        errors.append(f"{path}: expected type {schema['type']}, got {type(doc).__name__}")
        return errors
    if "const" in schema and doc != schema["const"]:
        errors.append(f"{path}: must equal {schema['const']!r}")
    if "enum" in schema and doc not in schema["enum"]:
        errors.append(f"{path}: {doc!r} not in {schema['enum']}")
    if isinstance(doc, str):
        if "minLength" in schema and len(doc) < schema["minLength"]:
            errors.append(f"{path}: shorter than minLength {schema['minLength']}")
        if "pattern" in schema and re.search(schema["pattern"], doc) is None:
            errors.append(f"{path}: does not match pattern {schema['pattern']!r}")
    if isinstance(doc, (int, float)) and not isinstance(doc, bool):
        if "minimum" in schema and doc < schema["minimum"]:
            errors.append(f"{path}: {doc!r} below minimum {schema['minimum']}")
    if isinstance(doc, dict):
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in doc:
                errors.append(f"{path}: missing required property {key!r}")
        for key, value in doc.items():
            if key in props:
                errors.extend(schema_errors(value, props[key], f"{path}.{key}"))
            elif schema.get("additionalProperties", True) is False:
                errors.append(f"{path}: additional property {key!r} not allowed")
    if isinstance(doc, list):
        if "minItems" in schema and len(doc) < schema["minItems"]:
            errors.append(f"{path}: fewer than minItems {schema['minItems']}")
        if "items" in schema:
            for index, item in enumerate(doc):
                errors.extend(schema_errors(item, schema["items"], f"{path}[{index}]"))
    return errors


def validate_document(doc: Any, schema: dict, what: str) -> None:
    """Raise :class:`SchemaError` naming the first violations of ``schema``."""
    errors = schema_errors(doc, schema)
    if errors:
        shown = "; ".join(errors[:5])
        raise SchemaError(f"{what} violates schema: {shown}")


# --------------------------------------------------------------------------- loading
def load_json(rel: str, root: str | os.PathLike[str] | None = None) -> Any:
    path = paths.repo_root(root) / rel
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_schema(rel: str, root: str | os.PathLike[str] | None = None) -> dict:
    schema = load_json(rel, root)
    if not isinstance(schema, dict):
        raise SchemaError(f"{rel} is not a JSON object")
    return schema


def load_inventory(root: str | os.PathLike[str] | None = None) -> dict:
    """Load and validate the release-gate metric inventory."""
    inventory = load_json(paths.INVENTORY_REL, root)
    validate_document(
        inventory, load_schema(paths.INVENTORY_SCHEMA_REL, root), paths.INVENTORY_REL
    )
    return inventory


def load_margin_table(root: str | os.PathLike[str] | None = None) -> dict:
    """Load and validate the frozen B07 margin table."""
    table = load_json(paths.MARGIN_TABLE_REL, root)
    validate_document(
        table, load_schema(paths.MARGIN_TABLE_SCHEMA_REL, root), paths.MARGIN_TABLE_REL
    )
    return table


# --------------------------------------------------------------------------- coverage
def gate_metric_ids(inventory: dict) -> list[str]:
    """Ids of the metrics the release gate reads, in inventory order."""
    return [str(m["id"]) for m in inventory.get("metrics", []) if m.get("gate") is True]


def table_by_id(table: dict) -> dict[str, dict]:
    """Margin rows keyed by metric id."""
    return {str(row["id"]): row for row in table.get("metrics", [])}


def coverage_gaps(inventory: dict, table: dict) -> list[str]:
    """Gate metrics the table fails to cover.

    A gap is a gate metric with no margin row, a row whose polarity contradicts
    the inventory, or a row without a numeric margin.  Each entry names the
    metric id first so callers can match on it.
    """
    polarity = {str(m["id"]): m.get("polarity") for m in inventory.get("metrics", [])}
    rows = table_by_id(table)
    gaps: list[str] = []
    for metric_id in gate_metric_ids(inventory):
        row = rows.get(metric_id)
        if row is None:
            gaps.append(f"{metric_id}: no margin row in table")
            continue
        margin = row.get("margin")
        if isinstance(margin, bool) or not isinstance(margin, (int, float)):
            gaps.append(f"{metric_id}: margin is not a number ({margin!r})")
        if row.get("polarity") != polarity.get(metric_id):
            gaps.append(
                f"{metric_id}: polarity {row.get('polarity')!r} contradicts inventory "
                f"{polarity.get(metric_id)!r}"
            )
    return gaps


def assert_table_covers_gate(inventory: dict, table: dict) -> None:
    """Raise :class:`MarginCoverageError` unless every gate metric has a margin."""
    gaps = coverage_gaps(inventory, table)
    if gaps:
        raise MarginCoverageError("margin table does not cover the gate: " + "; ".join(gaps))
    if len(gate_metric_ids(inventory)) == 0:
        raise MarginCoverageError("inventory declares no gate metrics")
