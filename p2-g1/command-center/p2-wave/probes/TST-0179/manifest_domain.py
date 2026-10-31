#!/usr/bin/env python3
"""TST-0179 measured layer: strict plugin-manifest parser + reference emitter.

STRICTEST-CLIENT semantics: the accepted top-level field set is closed; an
unknown field is a rejection whose error NAMES the field. The emitter is the
authoring-side counterpart: it must never emit a field outside the accepted
set.
"""
from __future__ import annotations

import json

ACCEPTED_TOP_LEVEL = {
    "name", "version", "description", "author", "license",
    "hooks", "skills", "commands", "agents", "mcpServers",
}


class StrictManifestError(Exception):
    def __init__(self, message: str, field: str | None = None):
        super().__init__(message)
        self.field = field


def parse_strict(text: str) -> dict:
    doc = json.loads(text)
    if not isinstance(doc, dict):
        raise StrictManifestError("manifest must be a JSON object")
    unknown = sorted(set(doc) - ACCEPTED_TOP_LEVEL)
    if unknown:
        raise StrictManifestError(
            "strict parser: unknown top-level field(s): " + ", ".join(unknown),
            field=unknown[0],
        )
    return doc


def parse_lenient(text: str) -> dict:
    """KNOWN-BROKEN counterpart: loads anything, no allowlist (detector control)."""
    return json.loads(text)


def emit(fields: dict) -> str:
    """Reference emitter: reject-at-authoring any field outside the accepted set."""
    bad = sorted(set(fields) - ACCEPTED_TOP_LEVEL)
    if bad:
        raise StrictManifestError("emitter refuses unknown top-level field(s): " + ", ".join(bad), field=bad[0])
    return json.dumps(fields, indent=2, sort_keys=True)
