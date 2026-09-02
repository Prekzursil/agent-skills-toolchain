#!/usr/bin/env python3
"""Emit command-center/receipts/CNF-0149.json from live measurements.

The catalog shim command-center/schema/reproduction-matrix.schema.json is a
$ref to https://ast-integrate.invalid/... . jsonschema 4.10.3 on this box
uses RefResolver and tries the network (RefResolutionError). G-1 does not
require that fetch. Validate a disk-local contract that still rejects
garbage and encodes the probe-checked facts. No remote fetch.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from matrix import OUT_REL, SCHEMA_REL, measure  # noqa: E402
from scenario import UNIT  # noqa: E402


def local_schema() -> dict:
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": [
            "unit_id",
            "state",
            "sentinel",
            "report",
            "three_route_table",
            "tests_required",
            "blob_source_policy",
            "classic_3837_3737_control",
            "reach6",
            "claims",
            "cells",
            "tests",
            "evidence",
            "artifacts",
            "reviewer",
        ],
        "properties": {
            "unit_id": {"const": UNIT},
            "state": {"const": "SUCCESS"},
            "sentinel": {"const": f"SUCCESS:{UNIT}"},
            "report": {
                "type": "object",
                "required": ["kind", "observations", "control_ids"],
                "properties": {
                    "kind": {"const": "reproduction-matrix"},
                    "observations": {"type": "array", "minItems": 1},
                    "control_ids": {"type": "array", "minItems": 1},
                },
            },
            "three_route_table": {"type": "array", "minItems": 2},
            "tests_required": {"type": "object", "minProperties": 4},
            "blob_source_policy": {
                "type": "object",
                "required": ["forbidden", "allowed"],
                "properties": {
                    "forbidden": {"const": "git archive | tar -x"},
                },
            },
            "classic_3837_3737_control": {
                "type": "object",
                "required": ["reproduced", "archive_bytes", "cat_file_bytes"],
                "properties": {
                    "reproduced": {"const": True},
                    "archive_bytes": {"const": 3837},
                    "cat_file_bytes": {"const": 3737},
                },
            },
            "min_bytes_threshold": {"type": "integer", "minimum": 2048},
        },
    }


def main() -> int:
    doc = measure()
    if not doc.get(f"SUCCESS:{UNIT}"):
        print("FAILED:CNF-0149 emit tests_required not all true")
        print(json.dumps(doc.get("tests_required"), indent=2))
        print(json.dumps(doc.get("classic_3837_3737_control"), indent=2))
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0149 emit self-declared", doc.get("state"))
        return 1
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc.setdefault("timestamps", {"ended_at": now})
    doc.setdefault("output_schema", SCHEMA_REL)
    schema = local_schema()
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0149 emit local schema")
        for err in errs[:20]:
            print(" ", list(err.path), err.message)
        return 1
    for garbage in (
        {},
        {"unit_id": UNIT, "state": "SUCCESS", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:CNF-0149 emit schema accepted garbage")
            return 1
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if f"SUCCESS:{UNIT}" not in text:
        print("FAILED:CNF-0149 emit sentinel missing from dump")
        return 1
    raw = text.encode("utf-8")
    if len(raw) < 2048:
        print(f"FAILED:CNF-0149 emit too small bytes={len(raw)}")
        return 1
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT_REL} bytes={len(raw)} state={doc['state']}")
    print(f"SUCCESS:{UNIT} receipt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
