#!/usr/bin/env python3
"""Authoring toolchain for Claude plugin manifests.

Refuses any top-level key that is not in the pinned vendor schema's
`properties` allowlist. That is the emit-side half of TST-0179: the
strict client must reject unknown fields, and this emitter must never
produce one.
"""
from __future__ import annotations

from typing import Any

from strict_parser import allowed_top_level_fields, load_vendor_schema

CLEAN_MANIFEST: dict[str, Any] = {
    "author": {"name": "ast-integrate"},
    "description": "Harness plugin manifest for TST-0179 strict-parser tests.",
    "keywords": ["harness", "strict-parser", "plugin-manifest"],
    "license": "MIT",
    "name": "ast-integrate-harness",
    "version": "1.0.0",
}

PLANTED_UNKNOWN_FIELD = "totally_unknown_field"


class UnknownFieldEmitError(ValueError):
    def __init__(self, fields: list[str]) -> None:
        self.fields = list(fields)
        super().__init__("emitter-refuses-unknown-field:" + ",".join(self.fields))


def emit_plugin_manifest(fields: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(CLEAN_MANIFEST if fields is None else fields)
    allowed = allowed_top_level_fields(load_vendor_schema())
    unknown = sorted(k for k in payload if k not in allowed)
    if unknown:
        raise UnknownFieldEmitError(unknown)
    if "name" not in payload or not str(payload["name"]).strip():
        raise ValueError("emitter-missing-required:name")
    return {k: payload[k] for k in sorted(payload)}


def schema_diff(emitted: dict[str, Any] | None = None) -> dict[str, Any]:
    """Independent signal (b): emitter field set is a subset of accepted keys."""
    accepted = sorted(allowed_top_level_fields(load_vendor_schema()))
    doc = emitted if emitted is not None else emit_plugin_manifest()
    emitted_keys = sorted(doc.keys())
    extra = sorted(k for k in emitted_keys if k not in set(accepted))
    missing_required = [k for k in ("name",) if k not in set(emitted_keys)]
    return {
        "accepted_field_set": accepted,
        "emitted_field_set": emitted_keys,
        "emitter_subset_of_accepted": extra == [] and missing_required == [],
        "extra_emitted_fields": extra,
        "missing_required": missing_required,
        "accepted_count": len(accepted),
        "emitted_count": len(emitted_keys),
    }
