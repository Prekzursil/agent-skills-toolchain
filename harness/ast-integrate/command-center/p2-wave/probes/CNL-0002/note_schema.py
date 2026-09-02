"""Disk-only validator for the catalog council-design-note output_schema.

System jsonschema 4.10.3 has no referencing.Registry (added in 4.18). A bare
Draft202012Validator(shim) follows $ref over HTTPS to ast-integrate.invalid
and raises RefResolutionError. This module maps those $ids onto the files
already on this worktree.
"""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/council-design-note.schema.json"
PROFILES_REL = "platform/schema/artifact-class-profiles.schema.json"
RECEIPT_REL = "platform/schema/receipt.schema.json"


def _load(rel: str) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def validator() -> Draft202012Validator:
    shim = _load(SCHEMA_REL)
    profiles = _load(PROFILES_REL)
    receipt = _load(RECEIPT_REL)
    store = {
        shim["$id"]: shim,
        profiles["$id"]: profiles,
        receipt["$id"]: receipt,
    }
    resolver = RefResolver(base_uri=shim["$id"], referrer=shim, store=store)
    return Draft202012Validator(shim, resolver=resolver)


def schema_errors(doc: dict) -> list[str]:
    out = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def design_payload(doc: dict) -> dict:
    """Domain block: report when present, else the document itself."""
    blob = doc.get("report")
    return blob if isinstance(blob, dict) else doc
