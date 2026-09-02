"""Offline catalog-schema + overlay checks for CNL-0099.

The declared output_schema is a generated $ref shim. Draft7Validator tries
to fetch https://ast-integrate.invalid over the network and fails. This
module resolves the three on-disk schemas by $id (no network) and adds an
overlay that type-checks false_positive_rate and requires detector_control.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_DECL = "command-center/schema/council-detector-spec.schema.json"
SCHEMA_FILES = (
    SCHEMA_DECL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)

OVERLAY: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["report"],
    "properties": {
        "report": {
            "type": "object",
            "required": [
                "kind",
                "false_positive_rate",
                "detector_control",
                "both_states",
                "claims",
            ],
            "properties": {
                "kind": {"const": "council-detector-spec"},
                "false_positive_rate": {"type": "number"},
                "detector_control": {
                    "type": "object",
                    "required": ["found_known_present", "fixture_id"],
                    "properties": {
                        "found_known_present": {"type": "boolean"},
                        "fixture_id": {"type": "string", "minLength": 1},
                    },
                },
                "both_states": {"type": "object"},
                "claims": {"type": "array", "minItems": 2},
            },
        }
    },
}


def _store() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for rel in SCHEMA_FILES:
        path = REPO / rel
        doc = json.loads(path.read_text(encoding="utf-8"))
        out["https://ast-integrate.invalid/" + rel] = doc
        out[path.resolve().as_uri()] = doc
        ident = doc.get("$id")
        if isinstance(ident, str) and ident:
            out[ident] = doc
    return out


def catalog_validator() -> Draft202012Validator:
    lib = REPO / "platform" / "lib"
    if str(lib) not in sys.path:
        sys.path.insert(0, str(lib))
    try:
        from schema_resolver import validator_for  # noqa: WPS433

        return validator_for(SCHEMA_DECL)
    except Exception:
        pass
    store = _store()
    shim = json.loads((REPO / SCHEMA_DECL).read_text(encoding="utf-8"))
    resolver = RefResolver.from_schema(shim, store=store)
    return Draft202012Validator(shim, resolver=resolver)


def _err_list(validator: Draft202012Validator, doc: Any) -> list[str]:
    out: list[str] = []
    for err in validator.iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def catalog_errors(doc: Any) -> list[str]:
    return _err_list(catalog_validator(), doc)


def overlay_errors(doc: Any) -> list[str]:
    return _err_list(Draft202012Validator(OVERLAY), doc)


def payload(doc: dict[str, Any]) -> dict[str, Any]:
    """Domain spec lives under report when the receipt envelope is used."""
    report = doc.get("report")
    if isinstance(report, dict) and "both_states" in report:
        return report
    return doc
