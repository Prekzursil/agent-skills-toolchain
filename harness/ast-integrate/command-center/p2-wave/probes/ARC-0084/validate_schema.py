"""Validate envelope/manifest instances against the frozen ARC-0084 schema."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CONTRACT = REPO / "command-center" / "phase4" / "contracts" / "ARC-0084.json"


def load_contract() -> dict[str, Any]:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def _validator(schema_doc: dict[str, Any], defn: str) -> Draft202012Validator:
    wrapper = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": schema_doc["$defs"],
        "$ref": f"#/$defs/{defn}",
    }
    return Draft202012Validator(wrapper)


def envelope_errors(instance: dict[str, Any], schema_doc: dict[str, Any] | None = None) -> list[str]:
    doc = schema_doc if schema_doc is not None else load_contract()
    v = _validator(doc, "artifact_envelope")
    return [e.message for e in v.iter_errors(instance)]


def check_contract_is_schema(schema_doc: dict[str, Any] | None = None) -> list[str]:
    doc = schema_doc if schema_doc is not None else load_contract()
    try:
        Draft202012Validator.check_schema(doc)
    except Exception as exc:  # noqa: BLE001 - surface validator text
        return [str(exc)]
    return []
