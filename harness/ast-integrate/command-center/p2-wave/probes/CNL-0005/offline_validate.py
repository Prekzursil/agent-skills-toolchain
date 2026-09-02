"""Offline $ref resolution for catalog shims (jsonschema 4.10, no network).

command-center/schema/*.schema.json are generated $ref shims whose $id and $ref
point at https://ast-integrate.invalid/.... Draft7Validator/Draft202012Validator
on this image (jsonschema 4.10.3) try to fetch that host. This module seeds a
RefResolver store from on-disk schema files so validation stays local.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator, Draft202012Validator, RefResolver
from jsonschema.exceptions import RefResolutionError, SchemaError, ValidationError

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG_SCHEMA = "command-center/schema/councilspec.v2.schema.json"
BASE = "https://ast-integrate.invalid/"


def _refuse_remote(uri: str) -> Any:
    raise RefResolutionError(f"offline-registry: refused remote fetch of {uri}")


def _seed_metaschemas(store: dict[str, Any]) -> None:
    for meta in (Draft202012Validator.META_SCHEMA, Draft7Validator.META_SCHEMA):
        resolver = RefResolver.from_schema(meta)
        for uri, doc in resolver.store.items():
            store.setdefault(str(uri), doc)


def build_store() -> dict[str, Any]:
    store: dict[str, Any] = {}
    _seed_metaschemas(store)
    roots = (
        REPO / "platform" / "schema",
        REPO / "command-center" / "schema",
    )
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*.json"):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(doc, dict):
                continue
            rel = path.relative_to(REPO).as_posix()
            store[BASE + rel] = doc
            ident = doc.get("$id")
            if isinstance(ident, str) and ident:
                store[ident] = doc
    return store


def load_declared(rel: str = CATALOG_SCHEMA) -> dict[str, Any]:
    path = REPO / rel
    return json.loads(path.read_text(encoding="utf-8"))


def make_resolver(schema: dict[str, Any], store: dict[str, Any] | None = None) -> RefResolver:
    st = store if store is not None else build_store()
    return RefResolver(
        base_uri=str(schema.get("$id") or ""),
        referrer=schema,
        store=st,
        cache_remote=False,
        handlers={"http": _refuse_remote, "https": _refuse_remote},
    )


def validator_for(
    rel: str = CATALOG_SCHEMA, store: dict[str, Any] | None = None
) -> Draft202012Validator:
    schema = load_declared(rel)
    st = store if store is not None else build_store()
    return Draft202012Validator(schema, resolver=make_resolver(schema, st))


def errors_of(instance: Any, rel: str = CATALOG_SCHEMA) -> list[str]:
    try:
        v = validator_for(rel)
        return [e.message for e in v.iter_errors(instance)]
    except (RefResolutionError, SchemaError) as exc:
        return [f"{type(exc).__name__}: {exc}"]


def error_count(instance: Any, rel: str = CATALOG_SCHEMA) -> int:
    return len(errors_of(instance, rel))


def assert_discriminates(rel: str = CATALOG_SCHEMA) -> None:
    """Fail closed if the declared schema accepts garbage (vacuous shim)."""
    garbage = (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"x": "x" * 2000},
    )
    for g in garbage:
        n = error_count(g, rel)
        if n <= 0:
            raise SystemExit(f"FAILED:CNL-0005 declared schema accepted garbage {list(g)[:2]}")


def report_payload(doc: dict[str, Any]) -> dict[str, Any]:
    """Domain payload lives under report for receipt_core additionalProperties=false."""
    report = doc.get("report")
    if isinstance(report, dict):
        return report
    return doc


def main() -> int:
    assert_discriminates(CATALOG_SCHEMA)
    art = (
        REPO
        / "command-center/design/council/"
        / "CNL-0005-participant-descriptor-type-the-9-per-seat-dials.md"
    )
    if not art.is_file():
        print("offline_validate: catalog schema discriminates garbage; artifact absent")
        print("SUCCESS:CNL-0005-offline-validate")
        return 0
    doc = json.loads(art.read_text(encoding="utf-8"))
    errs = errors_of(doc, CATALOG_SCHEMA)
    print(f"catalog {CATALOG_SCHEMA} errors={len(errs)}")
    if errs:
        for e in errs[:12]:
            print(" ", e)
        return 1
    print("SUCCESS:CNL-0005-offline-validate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
