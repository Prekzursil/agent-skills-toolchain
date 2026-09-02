"""Disk-only salvage-closure validation. Never fetch ast-integrate.invalid."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft7Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DECLARED = "command-center/schema/salvage-closure.schema.json"
STORE_FILES = (
    DECLARED,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def load_store() -> dict:
    store: dict = {}
    for rel in STORE_FILES:
        path = REPO / rel
        if not path.is_file():
            raise SystemExit(f"FAILED:BLD-0034 schema missing on disk: {rel}")
        doc = json.loads(path.read_text(encoding="utf-8"))
        store["https://ast-integrate.invalid/" + rel] = doc
        store[path.resolve().as_uri()] = doc
        sid = doc.get("$id")
        if isinstance(sid, str) and sid:
            store[sid] = doc
    return store


def validator() -> Draft7Validator:
    lib = REPO / "platform" / "lib"
    if str(lib) not in sys.path:
        sys.path.insert(0, str(lib))
    try:
        from schema_resolver import validator_for  # noqa: WPS433

        return validator_for(DECLARED)  # type: ignore[return-value]
    except Exception:
        pass
    store = load_store()
    schema = json.loads((REPO / DECLARED).read_text(encoding="utf-8"))
    base = str(schema.get("$id") or (REPO / DECLARED).resolve().as_uri())
    resolver = RefResolver(base_uri=base, referrer=schema, store=store)
    return Draft7Validator(schema, resolver=resolver)


def error_list(doc: object) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def assert_not_vacuous() -> None:
    v = validator()
    for garbage in (
        {},
        {"totally": "unrelated"},
        {"unit_id": "NOPE", "state": "SUCCESS"},
    ):
        if v.is_valid(garbage):
            raise SystemExit(
                f"FAILED:BLD-0034 schema vacuous on {list(garbage)[:3]}"
            )


def validate_or_die(doc: object) -> None:
    assert_not_vacuous()
    errs = error_list(doc)
    if errs:
        print("FAILED:BLD-0034 schema-invalid")
        for line in errs[:24]:
            print(" ", line)
        raise SystemExit(1)
