"""Local $ref store for command-center/schema/test-receipt.schema.json.

Never fetches ast-integrate.invalid. Used by emit_receipt and probe2.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SHIM_REL = "command-center/schema/test-receipt.schema.json"
SHIM_ID = "https://ast-integrate.invalid/command-center/schema/test-receipt.schema.json"
PROFILES_ID = "https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json"
RECEIPT_ID = "https://ast-integrate.invalid/platform/schema/receipt.schema.json"
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
)


def _load(rel: str) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def validator():
    shim = _load(SHIM_REL)
    profiles = _load("platform/schema/artifact-class-profiles.schema.json")
    receipt = _load("platform/schema/receipt.schema.json")
    store = {
        SHIM_ID: shim,
        PROFILES_ID: profiles,
        RECEIPT_ID: receipt,
    }
    resolver = jsonschema.RefResolver(base_uri=SHIM_ID, referrer=shim, store=store)
    return jsonschema.Draft7Validator(shim, resolver=resolver)


def iter_errors(doc) -> list:
    return sorted(validator().iter_errors(doc), key=lambda e: list(e.path))


def garbage_rejected() -> bool:
    v = validator()
    return all(list(v.iter_errors(item)) for item in GARBAGE)


def main() -> int:
    art = REPO / "command-center/receipts/TST-0101.json"
    if not art.is_file():
        print("FAILED:TST-0101-schema artifact missing")
        return 1
    doc = json.loads(art.read_text(encoding="utf-8"))
    errs = iter_errors(doc)
    if errs:
        print("FAILED:TST-0101-schema receipt errors")
        for err in errs[:12]:
            print(" ", list(err.path), err.message)
        return 1
    if not garbage_rejected():
        print("FAILED:TST-0101-schema accepted garbage")
        return 1
    print("schema_ok=True garbage_rejected=True")
    print("SUCCESS:TST-0101-schema local-ref-store")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
