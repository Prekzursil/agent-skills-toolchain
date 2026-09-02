"""Validate ADV-0143 receipts against the physical redistribution-adjudication schema.

jsonschema 4.10.3 follows $ref over the network. The catalog shim points at
https://ast-integrate.invalid/... which does not resolve. This module maps that
prefix onto files already on disk (no network, no ADV rebuild).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import unshadow as U  # noqa: E402

U.unshadow()
from jsonschema import Draft202012Validator, RefResolver  # noqa: E402

SCHEMA_REL = "command-center/schema/redistribution-adjudication.schema.json"
STORE_RELS = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {"schema_version": 1, "unit_id": "ADV-0143", "state": "SUCCESS"},
)
BASE = "https://ast-integrate.invalid/"


def disk_store(repo: Path | None = None) -> dict:
    root = repo or REPO
    store: dict = {}
    for rel in STORE_RELS:
        path = root / rel
        doc = json.loads(path.read_text(encoding="utf-8"))
        store[BASE + rel] = doc
        rid = doc.get("$id")
        if isinstance(rid, str) and rid:
            store[rid] = doc
        store[rel] = doc
        store[path.name] = doc
    return store


def validator(repo: Path | None = None) -> Draft202012Validator:
    root = repo or REPO
    schema = json.loads((root / SCHEMA_REL).read_text(encoding="utf-8"))
    resolver = RefResolver.from_schema(schema, store=disk_store(root))
    return Draft202012Validator(schema, resolver=resolver)


def error_messages(doc: object, repo: Path | None = None) -> list[str]:
    out: list[str] = []
    for err in validator(repo).iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def garbage_rejected(repo: Path | None = None) -> bool:
    v = validator(repo)
    for g in GARBAGE:
        if not list(v.iter_errors(g)):
            return False
    return True


def domain(doc: dict) -> dict:
    """Read the adjudication payload from report.* with a top-level fallback."""
    rep = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    return {
        "content_classes": doc.get("content_classes") or rep.get("content_classes") or [],
        "completeness_sample": doc.get("completeness_sample")
        or rep.get("completeness_sample")
        or {},
        "extent_control": doc.get("extent_control") or rep.get("extent_control") or {},
        "verdict_stability": doc.get("verdict_stability")
        or rep.get("verdict_stability")
        or {},
    }


def main() -> int:
    if len(sys.argv) >= 3 and sys.argv[1] == "--check":
        path = Path(sys.argv[2])
        if not path.is_file():
            print(f"FAILED:ADV-0143-schema missing {path}")
            return 1
        doc = json.loads(path.read_text(encoding="utf-8"))
        errs = error_messages(doc)
        if errs:
            print("FAILED:ADV-0143-schema-invalid")
            for line in errs[:25]:
                print(" ", line)
            return 1
        if not garbage_rejected():
            print("FAILED:ADV-0143-schema accepted garbage")
            return 1
        print("SUCCESS:ADV-0143-schema-valid")
        return 0
    if len(sys.argv) >= 2 and sys.argv[1] == "--self-test":
        if not garbage_rejected():
            print("FAILED:ADV-0143-schema self-test accepted garbage")
            return 1
        print("SUCCESS:ADV-0143-schema self-test garbage rejected")
        return 0
    print("usage: schema_check.py --check <receipt.json> | --self-test")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
