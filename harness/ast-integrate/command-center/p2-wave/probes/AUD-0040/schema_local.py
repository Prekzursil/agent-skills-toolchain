"""Compile the catalog audit-detector-control contract without network $ref.

The declared command-center/schema/audit-detector-control.schema.json is a
generated shim whose $ref is https://ast-integrate.invalid/... . jsonschema
4.10 Draft7Validator tries to fetch that host, so a direct validate() is a
detector that never constrains. Inline receipt $defs (BLD-0039 pattern).
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SHIM = "command-center/schema/audit-detector-control.schema.json"
RECEIPT = "platform/schema/receipt.schema.json"
KIND = "audit-detector-control"


def _load(rel: str) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def compiled_schema() -> dict:
    receipt = _load(RECEIPT)
    defs = receipt.get("$defs")
    if not isinstance(defs, dict) or "generic_report" not in defs:
        raise RuntimeError("receipt.schema.json missing $defs.generic_report")
    return {
        "$id": (
            "https://ast-integrate.invalid/command-center/p2-wave/probes/"
            "AUD-0040/audit-detector-control.local.json"
        ),
        "allOf": [
            {"$ref": "#/$defs/generic_report"},
            {
                "type": "object",
                "properties": {
                    "report": {
                        "required": ["kind"],
                        "properties": {"kind": {"const": KIND}},
                    }
                },
            },
        ],
        "$defs": defs,
    }


def validator() -> jsonschema.Draft7Validator:
    return jsonschema.Draft7Validator(compiled_schema())


def errors(doc: object) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def rejects_garbage() -> bool:
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"unit_id": "AUD-0040", "state": "SUCCESS", "sentinel": "SUCCESS:AUD-0040"},
    ):
        if not errors(garbage):
            return False
    return True


def folded_measurement(doc: dict) -> dict:
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    inner = report.get("measurement")
    if isinstance(inner, dict) and inner:
        return inner
    top = doc.get("measurement")
    return top if isinstance(top, dict) else {}


def folded_detector_control(doc: dict) -> dict:
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    inner = report.get("detector_control")
    if isinstance(inner, dict) and inner:
        return inner
    top = doc.get("detector_control")
    return top if isinstance(top, dict) else {}
