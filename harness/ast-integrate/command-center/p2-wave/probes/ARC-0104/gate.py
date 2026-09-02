#!/usr/bin/env python3
"""Three-way contract parity: docs vs schema vs implementation.

A divergence is never a single number. Each finding is stored under a named
direction:

  docs_not_schema   documented field absent from the schema
  docs_not_impl     documented field absent from the consumer/instance
  schema_not_docs   schema field with no documentation
  impl_not_docs     implemented field with no documentation
  schema_not_impl   schema field the consumer does not use
  impl_not_schema   implemented field not in the schema
  default_mismatch  same field name, different default on two or more surfaces

A total of zero on a tree that has never had this gate, without a planted
documented-but-absent control having fired, is DETECTOR-FAILURE — not CLEAN.
"""
from __future__ import annotations

import json
from typing import Any, Iterable, Mapping

DIRECTION_KEYS = (
    "docs_not_schema",
    "docs_not_impl",
    "schema_not_docs",
    "impl_not_docs",
    "schema_not_impl",
    "impl_not_schema",
    "default_mismatch",
)

ABSENT = object()
PLANTED_FIELD = "planted_canary_field"


def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _aset(names: Iterable[str]) -> set[str]:
    return {str(n).strip() for n in names if str(n).strip()}


def direction_bucket(fields: Iterable[str]) -> dict[str, Any]:
    items = sorted(_aset(fields))
    return {"count": len(items), "fields": items}


def empty_directions() -> dict[str, dict[str, Any]]:
    return {key: direction_bucket([]) for key in DIRECTION_KEYS}


def compare_surfaces(
    docs_fields: Iterable[str],
    schema_fields: Iterable[str],
    impl_fields: Iterable[str],
    *,
    docs_defaults: Mapping[str, Any] | None = None,
    schema_defaults: Mapping[str, Any] | None = None,
    impl_defaults: Mapping[str, Any] | None = None,
    qualify: str = "",
) -> dict[str, dict[str, Any]]:
    """Return the seven named directions. Never collapses to one integer."""
    docs = _aset(docs_fields)
    schema = _aset(schema_fields)
    impl = _aset(impl_fields)
    prefix = f"{qualify}." if qualify else ""

    def q(names: Iterable[str]) -> list[str]:
        return [f"{prefix}{n}" for n in sorted(_aset(names))]

    dd = dict(docs_defaults or {})
    sd = dict(schema_defaults or {})
    idd = dict(impl_defaults or {})
    mismatches: list[str] = []
    for field in sorted(set(dd) | set(sd) | set(idd)):
        present = {}
        if field in dd:
            present["docs"] = _canon(dd[field])
        if field in sd:
            present["schema"] = _canon(sd[field])
        if field in idd:
            present["impl"] = _canon(idd[field])
        if len(set(present.values())) > 1:
            mismatches.append(f"{prefix}{field}")

    return {
        "docs_not_schema": direction_bucket(q(docs - schema)),
        "docs_not_impl": direction_bucket(q(docs - impl)),
        "schema_not_docs": direction_bucket(q(schema - docs)),
        "impl_not_docs": direction_bucket(q(impl - docs)),
        "schema_not_impl": direction_bucket(q(schema - impl)),
        "impl_not_schema": direction_bucket(q(impl - schema)),
        "default_mismatch": direction_bucket(mismatches),
    }


def merge_directions(parts: Iterable[Mapping[str, Mapping[str, Any]]]) -> dict[str, dict[str, Any]]:
    acc: dict[str, set[str]] = {key: set() for key in DIRECTION_KEYS}
    for part in parts:
        for key in DIRECTION_KEYS:
            bucket = part.get(key) or {}
            acc[key].update(bucket.get("fields") or [])
    return {key: direction_bucket(acc[key]) for key in DIRECTION_KEYS}


def direction_total(directions: Mapping[str, Mapping[str, Any]]) -> int:
    """Sum of per-direction counts. Caption only — never the stored result."""
    return sum(int((directions.get(k) or {}).get("count") or 0) for k in DIRECTION_KEYS)


def dominant_direction(directions: Mapping[str, Mapping[str, Any]]) -> tuple[str, int]:
    ranked = sorted(
        ((k, int((directions.get(k) or {}).get("count") or 0)) for k in DIRECTION_KEYS),
        key=lambda kv: (-kv[1], kv[0]),
    )
    return ranked[0]


def live_verdict(directions: Mapping[str, Mapping[str, Any]], *, control_fired: bool) -> str:
    total = direction_total(directions)
    if total == 0 and not control_fired:
        return "DETECTOR-FAILURE"
    if total == 0:
        return "CLEAN-AFTER-CONTROL"
    return "DIVERGENT"


def compare_fixture_bundle(bundle: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return compare_surfaces(
        bundle.get("fields") and bundle["fields"] or [],
        [],
        [],
    )


def surfaces_from_fixture(node: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    docs = node["docs"]
    schema = node["schema"]
    impl = node["impl"]
    return compare_surfaces(
        docs.get("fields") or [],
        schema.get("fields") or [],
        impl.get("fields") or [],
        docs_defaults=docs.get("defaults") or {},
        schema_defaults=schema.get("defaults") or {},
        impl_defaults=impl.get("defaults") or {},
        qualify="fixture",
    )


def artifact_section(doc: Mapping[str, Any], key: str, default: Any = None) -> Any:
    """Read a payload key from the conformance receipt.

    receipt_core forbids extra top-level keys, so the live payload lives under
    report (or extensions). Older drafts stored the same keys at the root;
    those still win if present so a prior on-disk shape keeps working.
    """
    if not isinstance(doc, Mapping):
        return default
    if key in doc and doc[key] is not None:
        return doc[key]
    report = doc.get("report")
    if isinstance(report, Mapping) and key in report:
        return report[key]
    ext = doc.get("extensions")
    if isinstance(ext, Mapping) and key in ext:
        return ext[key]
    return default


def assert_named_directions(directions: Mapping[str, Any]) -> None:
    if not isinstance(directions, dict):
        raise AssertionError("directions must be an object, never a single number")
    missing = [k for k in DIRECTION_KEYS if k not in directions]
    if missing:
        raise AssertionError(f"direction keys missing: {missing}")
    for key in DIRECTION_KEYS:
        bucket = directions[key]
        if not isinstance(bucket, dict):
            raise AssertionError(f"{key} must be an object with count+fields")
        if "count" not in bucket or "fields" not in bucket:
            raise AssertionError(f"{key} missing count or fields")
        if not isinstance(bucket["count"], int):
            raise AssertionError(f"{key}.count is not an int")
        if bucket["count"] != len(bucket["fields"]):
            raise AssertionError(f"{key}.count {bucket['count']} != len(fields)")
    extra_numbers = [k for k, v in directions.items() if isinstance(v, (int, float))]
    if extra_numbers:
        raise AssertionError(f"bare numeric direction keys forbidden: {extra_numbers}")
