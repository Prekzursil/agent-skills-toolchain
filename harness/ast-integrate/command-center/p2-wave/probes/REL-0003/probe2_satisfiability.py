#!/usr/bin/env python3
"""Probe 2: catalog id-lookup satisfiability + missing-default negative control.

Mechanically different from probe 1: does not parse OWNER-DECISIONS.md questions.
Looks up each named receipt's unit_id in WORK-UNIT-CATALOG.json and requires the
validator to reject a packet that omits default_if_unanswered.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import validator as V  # noqa: E402

ART = REPO / "command-center/receipts/REL-0003.json"
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
CATALOG_SCHEMA = REPO / "command-center/schema/owner-decision-packet.schema.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:REL-0003-probe2 packet missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    if not CATALOG_SCHEMA.is_file() or CATALOG_SCHEMA.stat().st_size <= 0:
        print("FAILED:REL-0003-probe2 catalog output_schema missing")
        return 1
    schema = V.load_schema()
    jsonschema.Draft7Validator.check_schema(schema)

    if "SUCCESS:REL-0003" not in json.dumps(doc):
        print("FAILED:REL-0003-probe2 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:REL-0003-probe2 self-declared {doc.get('state')}")
        return 1

    live = V.satisfiability_errors(doc, catalog)
    rows = V.named_receipts(doc)
    print(f"named_receipts={len(rows)}")
    for row in rows:
        uid = row.get("unit_id")
        path = row.get("path")
        unit = V.catalog_index(catalog).get(str(uid))
        cat_path = (unit or {}).get("output_path")
        print(f"lookup {uid} catalog_output_path={cat_path} named={path}")
    if live:
        print("FAILED:REL-0003-probe2 live named receipts failed id lookup")
        for e in live:
            print(" ", e)
        return 1

    unknown = copy.deepcopy(doc)
    unknown["recommendation"]["named_receipts"] = [
        {
            "unit_id": "NO-SUCH-UNIT",
            "path": "command-center/receipts/NO-SUCH-UNIT.json",
            "role": "invented",
        },
        rows[1],
        rows[2],
    ]
    unknown_errs = V.satisfiability_errors(unknown, catalog)
    print(f"unknown_unit_errors={len(unknown_errs)}")
    if not any("NO-SUCH-UNIT" in e or "catalog id lookup missed" in e for e in unknown_errs):
        print("FAILED:REL-0003-probe2 unknown unit was not caught by id lookup")
        return 1

    mismatch = copy.deepcopy(doc)
    mismatch["recommendation"]["named_receipts"][0]["path"] = "command-center/receipts/WRONG.json"
    mismatch_errs = V.satisfiability_errors(mismatch, catalog)
    print(f"path_mismatch_errors={len(mismatch_errs)}")
    if not mismatch_errs:
        print("FAILED:REL-0003-probe2 path mismatch was not caught")
        return 1

    if not V.reject_missing_default(doc, schema):
        print("FAILED:REL-0003-probe2 missing default_if_unanswered was accepted")
        return 1
    mutant = copy.deepcopy(doc)
    mutant.pop("default_if_unanswered", None)
    missing_errs = V.schema_errors(mutant, schema)
    print(f"missing_default_schema_errors={len(missing_errs)}")
    if not any("default_if_unanswered" in e for e in missing_errs):
        print("FAILED:REL-0003-probe2 validator did not name default_if_unanswered")
        return 1

    garbage_rejected = 0
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"unit_id": "REL-0003", "state": "SUCCESS"},
    ):
        if V.schema_errors(garbage, schema):
            garbage_rejected += 1
        else:
            print(f"FAILED:REL-0003-probe2 schema accepted garbage {garbage}")
            return 1
    print(f"schema_garbage_rejected={garbage_rejected}/3")
    print("SUCCESS:REL-0003-probe2 catalog-id-lookup and missing-default control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
