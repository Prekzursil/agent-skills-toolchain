#!/usr/bin/env python3
"""Offline schema registry + pinned jsonschema validator for ARC-0102.

Canonical $id values live in schemas/*.json. Cross-schema $ref is resolved from
the in-memory store only. Remote fetch is refused even when the process still
has network: a validation step that resolves a remote meta-schema is a network
dependency in a gate.
"""
from __future__ import annotations

import json
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import Draft202012Validator, Draft7Validator, RefResolver
from jsonschema.exceptions import RefResolutionError

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PIN_PATH = HERE / "pin.json"
SCHEMA_DIR = HERE / "schemas"
FIXTURE_DIR = HERE / "fixtures"

IDENTITY_ID = "https://ast-integrate.invalid/schema/common/identity.json"
ENVELOPE_ID = "https://ast-integrate.invalid/schema/artifact-envelope.json"
CASE_ID = "https://ast-integrate.invalid/schema/conformance-case.json"
SHIM_ID = (
    "https://ast-integrate.invalid/command-center/schema/conformance-report.schema.json"
)
CATALOG_SCHEMA_RELS = (
    "command-center/schema/conformance-report.schema.json",
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


class PinMismatch(RuntimeError):
    """Installed jsonschema does not match the pin file. The gate must fail closed."""


def load_pin() -> dict:
    return json.loads(PIN_PATH.read_text(encoding="utf-8"))


def observed_jsonschema_version() -> str:
    try:
        return version("jsonschema")
    except PackageNotFoundError as exc:
        raise PinMismatch("jsonschema is not installed") from exc


def assert_pin() -> dict:
    pin = load_pin()
    pinned = str(pin.get("pinned_version") or "")
    observed = observed_jsonschema_version()
    record = {
        "package": pin.get("package") or "jsonschema",
        "pinned_version": pinned,
        "observed_version": observed,
        "match": pinned == observed,
    }
    if not pinned:
        raise PinMismatch("pin.json has no pinned_version")
    if pinned != observed:
        raise PinMismatch(
            f"jsonschema pin mismatch: pinned={pinned} observed={observed}"
        )
    return record


def _refuse_remote(uri: str) -> Any:
    raise RefResolutionError(f"offline-registry: refused remote fetch of {uri}")


def _seed_official_metaschemas(store: dict[str, Any]) -> list[str]:
    """Copy the PINNED package's in-memory meta-schemas. No network."""
    seeded: list[str] = []
    for meta in (Draft202012Validator.META_SCHEMA, Draft7Validator.META_SCHEMA):
        resolver = RefResolver.from_schema(meta)
        for uri, doc in resolver.store.items():
            key = str(uri)
            if key not in store:
                store[key] = doc
                seeded.append(key)
    return sorted(set(seeded))


def build_store() -> dict[str, Any]:
    """Canonical-id store: official meta-schemas + this unit's schema files."""
    assert_pin()
    store: dict[str, Any] = {}
    _seed_official_metaschemas(store)
    for path in sorted(SCHEMA_DIR.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        ident = doc.get("$id")
        if not isinstance(ident, str) or not ident:
            raise RuntimeError(f"schema missing $id: {path}")
        store[ident] = doc
        store[path.as_posix()] = doc
        store[str(path.relative_to(REPO)).replace("\\", "/")] = doc
    return store


def canonical_ids(store: dict[str, Any] | None = None) -> list[str]:
    st = store if store is not None else build_store()
    return sorted(k for k in st if k.startswith("https://") or k.startswith("http://"))


def seed_disk_schemas(
    store: dict[str, Any], rels: tuple[str, ...] = CATALOG_SCHEMA_RELS
) -> list[str]:
    """Index local schema files by $id. No network."""
    seeded: list[str] = []
    for rel in rels:
        path = REPO / rel
        if not path.is_file():
            raise RuntimeError(f"offline-registry: missing schema file {rel}")
        doc = json.loads(path.read_text(encoding="utf-8"))
        ident = doc.get("$id")
        if isinstance(ident, str) and ident:
            store[ident] = doc
            seeded.append(ident)
        store[rel] = doc
        store[path.as_posix()] = doc
        https_alias = "https://ast-integrate.invalid/" + rel.replace("\\", "/")
        store[https_alias] = doc
        file_alias = path.resolve().as_uri()
        store[file_alias] = doc
    return seeded


def catalog_output_schema_offline(store: dict[str, Any] | None = None) -> dict:
    """Resolve the catalog output_schema $ref from disk. Must not fetch.

    The generated shim at command-center/schema/conformance-report.schema.json
    $refs a physical profile. A bare Draft7Validator follows that URL and
    becomes a network dependency. This path loads the three local files into
    the store and refuses http(s) retrieve.
    """
    st = dict(store) if store is not None else build_store()
    seeded = seed_disk_schemas(st)
    shim = st.get(SHIM_ID) or st.get(CATALOG_SCHEMA_RELS[0])
    if not isinstance(shim, dict):
        raise RefResolutionError(f"offline-registry: unknown schema {SHIM_ID}")
    ref = shim.get("$ref")
    if not isinstance(ref, str) or not ref:
        raise RuntimeError("conformance-report shim has no $ref")
    resolver = make_resolver(shim, st)
    url, resolved = resolver.resolve(ref)
    validator = Draft202012Validator(shim, resolver=resolver)
    garbage_errs = list(
        validator.iter_errors({"totally": "unrelated", "passing_tests": 999999})
    )
    empty_errs = list(validator.iter_errors({}))
    empty_msgs = [e.message for e in empty_errs[:12]]
    garbage_msgs = [e.message for e in garbage_errs[:12]]
    looks_like_receipt = any("schema_version" in m for m in empty_msgs)
    return {
        "seeded_ids": seeded,
        "shim_id": SHIM_ID,
        "ref": ref,
        "resolved_url": url,
        "resolved_has_allOf": isinstance(resolved, dict) and "allOf" in resolved,
        "garbage_rejected": bool(garbage_errs),
        "empty_rejected": bool(empty_errs),
        "empty_messages": empty_msgs,
        "garbage_messages": garbage_msgs,
        "looks_like_receipt_core": looks_like_receipt,
        "ok": bool(garbage_errs)
        and bool(empty_errs)
        and looks_like_receipt
        and bool(isinstance(resolved, dict) and "allOf" in resolved),
    }


def make_resolver(schema: dict, store: dict[str, Any]) -> RefResolver:
    return RefResolver(
        base_uri=str(schema.get("$id") or ""),
        referrer=schema,
        store=store,
        cache_remote=False,
        handlers={"http": _refuse_remote, "https": _refuse_remote},
    )


def resolve_schema(schema_ref: str, store: dict[str, Any]) -> dict:
    if schema_ref in store and isinstance(store[schema_ref], dict):
        return store[schema_ref]
    path = REPO / schema_ref.split("#", 1)[0]
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    raise RefResolutionError(f"offline-registry: unknown schema {schema_ref}")


def validate_against(instance: Any, schema_ref: str, store: dict[str, Any]) -> list[str]:
    schema = resolve_schema(schema_ref, store)
    validator = Draft202012Validator(schema, resolver=make_resolver(schema, store))
    return [e.message for e in validator.iter_errors(instance)]


def load_json(name: str) -> Any:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def suite_cases() -> list[dict]:
    """Fixed accept/reject matrix. Cross-schema $ref is exercised by CASE_ID."""
    return [
        {
            "id": "envelope-valid",
            "schema": ENVELOPE_ID,
            "instance": load_json("envelope.valid.json"),
            "want_valid": True,
        },
        {
            "id": "envelope-missing-hash",
            "schema": ENVELOPE_ID,
            "instance": load_json("envelope.invalid-no-hash.json"),
            "want_valid": False,
        },
        {
            "id": "envelope-garbage",
            "schema": ENVELOPE_ID,
            "instance": {"totally": "unrelated", "passing_tests": 999999},
            "want_valid": False,
        },
        {
            "id": "envelope-unregistered",
            "schema": ENVELOPE_ID,
            "instance": {
                **load_json("envelope.valid.json"),
                "registered": False,
            },
            "want_valid": False,
        },
        {
            "id": "case-valid-two-hop",
            "schema": CASE_ID,
            "instance": load_json("case.valid.json"),
            "want_valid": True,
        },
        {
            "id": "case-invalid-nested-digest",
            "schema": CASE_ID,
            "instance": load_json("case.invalid.json"),
            "want_valid": False,
        },
    ]


def run_suite(store: dict[str, Any] | None = None) -> dict:
    st = store if store is not None else build_store()
    rows = []
    mismatches = []
    for case in suite_cases():
        errors = validate_against(case["instance"], case["schema"], st)
        valid = len(errors) == 0
        row = {
            "id": case["id"],
            "schema": case["schema"],
            "valid": valid,
            "error_count": len(errors),
            "errors": errors[:8],
            "want_valid": case["want_valid"],
        }
        rows.append(row)
        if valid != case["want_valid"]:
            mismatches.append(case["id"])
    return {
        "rows": rows,
        "fingerprint": [(r["id"], r["valid"], r["error_count"]) for r in rows],
        "mismatches": mismatches,
        "ok": not mismatches,
    }


def refuse_unregistered_ref(store: dict[str, Any] | None = None) -> dict:
    """A $ref whose URI is not in the store must refuse, not fetch."""
    st = store if store is not None else build_store()
    orphan = {
        "$id": "https://ast-integrate.invalid/schema/orphan.json",
        "type": "object",
        "properties": {
            "x": {"$ref": "https://example.invalid/not-in-registry.json"},
        },
    }
    try:
        errors = validate_against({"x": {}}, orphan["$id"], {**st, orphan["$id"]: orphan})
        return {
            "refused": False,
            "error": None,
            "unexpected_errors": errors,
        }
    except RefResolutionError as exc:
        msg = str(exc)
        return {
            "refused": "offline-registry: refused remote fetch" in msg
            or "not-in-registry.json" in msg,
            "error": msg[:500],
            "unexpected_errors": None,
        }


def build_registry() -> dict[str, Any]:
    """Name used by ready_units / historical probes. Returns the URI store."""
    return build_store()


def validate_artifact(doc: Any, schema_ref: str) -> list[str]:
    """Return error strings; empty means valid. Offline, pin-gated."""
    return validate_against(doc, schema_ref, build_store())
