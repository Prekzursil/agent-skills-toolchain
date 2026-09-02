#!/usr/bin/env python3
"""Write command-center/confirmation/CNF-0002-independence-predicate.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.validators import RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from report import dump_report  # noqa: E402

OUT = REPO / "command-center/confirmation/CNF-0002-independence-predicate.json"
SCHEMA = REPO / "command-center/schema/confirmation-policy.schema.json"
PHYSICAL = [
    "command-center/schema/confirmation-policy.schema.json",
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
]


def offline_validator() -> Draft202012Validator:
    store: dict = {}
    for rel in PHYSICAL:
        path = REPO / rel
        doc = json.loads(path.read_text(encoding="utf-8"))
        store[path.resolve().as_uri()] = doc
        store[rel] = doc
        sid = doc.get("$id")
        if isinstance(sid, str) and sid:
            store[sid] = doc
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    resolver = RefResolver(base_uri=str(schema.get("$id") or SCHEMA.as_uri()), referrer=schema, store=store)
    return Draft202012Validator(schema, resolver=resolver)


def main() -> int:
    text = dump_report()
    doc = json.loads(text)
    validator = offline_validator()
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0002 schema-invalid")
        for err in errs[:25]:
            print(" ", list(err.path), err.message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"unit_id": "CNF-0002", "state": "SUCCESS"},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:CNF-0002 schema accepted garbage")
            return 1
    if "SUCCESS:CNF-0002 emitted only when" not in text:
        print("FAILED:CNF-0002 catalog completion_sentinel missing from artifact")
        return 1
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    if report.get("empty_set_read_as_pass") is not False:
        print("FAILED:CNF-0002 empty-set-read-as-pass was not stated false")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0002 self-declared {doc.get('state')}")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(REPO).as_posix()} bytes={len(text.encode('utf-8'))}")
    print("SUCCESS:CNF-0002 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
