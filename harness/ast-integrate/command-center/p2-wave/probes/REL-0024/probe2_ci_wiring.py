#!/usr/bin/env python3
"""Probe 2: deleting the fix turns the wired B08 suite red; schema holds.

Independent of probe 1's printout: re-runs delete-fix CI and validates
the receipt against regression-seed-receipt.schema.json, including a
garbage-document control so the schema is not a tautology.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from engine import run  # noqa: E402

ART = REPO / "command-center/receipts/REL-0024.json"
SCHEMA = REPO / "command-center/schema/regression-seed-receipt.schema.json"


def main() -> int:
    live = run()
    deleted = live["delete_fix_ci"]
    if deleted.get("suite_outcome") != "RED":
        print("FAILED:REL-0024-probe2 delete-fix suite was not RED", deleted)
        return 1
    if not deleted.get("proves_wiring_live"):
        print("FAILED:REL-0024-probe2 wiring not proved live")
        return 1
    if int(deleted.get("n_red") or 0) < 1:
        print("FAILED:REL-0024-probe2 n_red < 1", deleted)
        return 1
    if live["b08_wiring"].get("post_fix_suite_outcome") != "GREEN":
        print("FAILED:REL-0024-probe2 post-fix suite not GREEN")
        return 1
    if not live["b08_wiring"].get("live"):
        print("FAILED:REL-0024-probe2 b08_wiring.live is false")
        return 1
    if deleted.get("fix_deleted_sha") != live.get("pre_sha"):
        print("FAILED:REL-0024-probe2 delete SHA is not the pre-fix SHA")
        return 1

    if not ART.is_file():
        print("FAILED:REL-0024-probe2 receipt missing")
        return 1
    rec = json.loads(ART.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(rec), key=lambda e: list(e.path))
    if errs:
        print("FAILED:REL-0024-probe2 schema errors")
        for e in errs[:12]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in ({}, {"unit_id": "NOPE"}, {"blob": "x" * 2000}):
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:REL-0024-probe2 schema accepted garbage {list(garbage)[:3]}")
            return 1
    if rec.get("state") == "BLOCKED":
        print("FAILED:REL-0024-probe2 receipt BLOCKED")
        return 1
    if rec.get("delete_fix_ci", {}).get("suite_outcome") != "RED":
        print("FAILED:REL-0024-probe2 receipt delete_fix_ci not RED")
        return 1
    if rec.get("b08_wiring", {}).get("suite_id") != "B08-seeded-regression":
        print("FAILED:REL-0024-probe2 suite_id mismatch")
        return 1
    if "SUCCESS:REL-0024" not in ART.read_text(encoding="utf-8"):
        print("FAILED:REL-0024-probe2 sentinel absent")
        return 1

    print(
        json.dumps(
            {
                "probe": "probe2-delete-fix-ci",
                "unit_id": "REL-0024",
                "delete_fix_suite_outcome": "RED",
                "post_fix_suite_outcome": "GREEN",
                "n_red_after_delete": deleted["n_red"],
                "schema_ok": True,
                "garbage_rejected": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"delete_fix=RED post_fix=GREEN n_red={deleted['n_red']} schema_ok=True"
    )
    print("SUCCESS:REL-0024-probe2 delete-fix CI wiring and schema")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
