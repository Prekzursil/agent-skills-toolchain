"""Validate a test-quality-census document against the shipped schema."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA = REPO / "command-center" / "schema" / "test-quality-census.schema.json"


def load_schema() -> dict:
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


def validate_doc(doc: dict) -> list[str]:
    validator = jsonschema.Draft7Validator(load_schema())
    return [
        f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
        for e in validator.iter_errors(doc)
    ]


def garbage_rejected() -> bool:
    schema = load_schema()
    validator = jsonschema.Draft7Validator(schema)
    probes = [
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    ]
    return all(bool(list(validator.iter_errors(p))) for p in probes)


def main() -> int:
    if len(sys.argv) < 2:
        print("FAILED:validate usage validate_schema.py <doc.json>")
        return 2
    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"FAILED:validate missing {path}")
        return 1
    if not garbage_rejected():
        print("FAILED:validate schema is vacuous")
        return 1
    doc = json.loads(path.read_text(encoding="utf-8"))
    errs = validate_doc(doc)
    if errs:
        print("FAILED:validate schema errors")
        for e in errs[:12]:
            print(f"  {e}")
        return 1
    print(f"SUCCESS:validate {path.as_posix()} schema-ok discriminating=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
