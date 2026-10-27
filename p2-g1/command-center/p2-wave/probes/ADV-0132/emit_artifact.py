#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0132-consensus-vs-test-divergence.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import study as S  # noqa: E402

REPO = S.REPO
OUT = S.OUT_REL
SCHEMA = S.SCHEMA_REL


def main() -> int:
    doc = S.build_document()
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:ADV-0132 schema errors")
        for err in errs[:20]:
            print(" ", list(err.path), err.message)
        return 1
    for garbage in (
        {"totally": "unrelated"},
        {"blob": "x" * 200},
        {},
        {"unit_id": "ADV-0132", "state": "SUCCESS"},
    ):
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:ADV-0132 schema accepted garbage {list(garbage)[:2]}")
            return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:ADV-0132 emit state={doc.get('state')}")
        return 1
    if not doc["pre_registration"]["every_prediction_precedes_run"]:
        print("FAILED:ADV-0132 predictions did not precede execution")
        return 1
    if not doc["negative_control"]["agrees_with_preexisting_tests"]:
        print("FAILED:ADV-0132 negative control did not agree")
        return 1
    if not doc["mutation_control"]["went_red"]:
        print("FAILED:ADV-0132 mutation control did not go red")
        return 1
    if S.CATALOG_SENTINEL not in doc["answer"] or S.CATALOG_SENTINEL not in doc["sentinel"]:
        print("FAILED:ADV-0132 catalog sentinel missing from fields")
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if S.CATALOG_SENTINEL not in text:
        print("FAILED:ADV-0132 catalog sentinel absent from serialized artifact")
        return 1
    out.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} bytes={out.stat().st_size}")
    print(
        f"headline refuted={doc['headline']['refuted']}/{doc['headline']['n']} "
        f"went_red={doc['mutation_control']['went_red']}"
    )
    print("SUCCESS:ADV-0132 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
