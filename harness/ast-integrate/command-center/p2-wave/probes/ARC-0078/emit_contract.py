#!/usr/bin/env python3
"""Write command-center/phase4/contracts/ARC-0078.json (JSON Schema 2020-12)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from clauses import CLAUSE_STRINGS, CONTRACT_REL, SENTINEL  # noqa: E402
from schema import build_schema  # noqa: E402

REPO = HERE.parents[3]
OUT = REPO / CONTRACT_REL


def _check(doc: dict) -> bool:
    import jsonschema

    try:
        jsonschema.Draft202012Validator.check_schema(doc)
    except Exception as exc:
        print(f"FAILED:ARC-0078 check_schema {type(exc).__name__}: {exc}")
        return False
    v = jsonschema.Draft202012Validator(doc)
    garbage = (
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
        {"name": "x"},
        {"$schema": "https://json-schema.org/draft/2020-12/schema"},
    )
    for g in garbage:
        errs = list(v.iter_errors(g))
        if not errs:
            print(f"FAILED:ARC-0078 schema-document-vacuous on {repr(g)[:80]}")
            return False
    return True


def main() -> int:
    doc = build_schema()
    if not _check(doc):
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    missing = [c for c in CLAUSE_STRINGS if c not in text]
    if missing:
        print(f"FAILED:ARC-0078 emit missing clauses {missing[:3]}")
        return 1
    if SENTINEL not in text:
        print("FAILED:ARC-0078 emit sentinel absent")
        return 1
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {CONTRACT_REL} bytes={len(text.encode('utf-8'))}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
