"""Disk-only validator for command-center/schema/security-report.schema.json.

System jsonschema 4.10.3 has no referencing.Registry. A bare Draft7Validator
on the shim follows https://ast-integrate.invalid and raises RefResolutionError.
This module maps those $ids onto files already on this worktree.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SHIM = "command-center/schema/security-report.schema.json"
PROFILES = "platform/schema/artifact-class-profiles.schema.json"
RECEIPT = "platform/schema/receipt.schema.json"
FRAGMENT = "#/$defs/security-report"


def _load(rel: str) -> dict[str, Any]:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def validator() -> Draft202012Validator:
    shim = _load(SHIM)
    profiles = _load(PROFILES)
    receipt = _load(RECEIPT)
    store = {
        shim["$id"]: shim,
        profiles["$id"]: profiles,
        receipt["$id"]: receipt,
        "https://ast-integrate.invalid/" + SHIM: shim,
        "https://ast-integrate.invalid/" + PROFILES: profiles,
        "https://ast-integrate.invalid/" + RECEIPT: receipt,
    }
    schema = {"$ref": profiles["$id"] + FRAGMENT}
    resolver = RefResolver(base_uri=profiles["$id"], referrer=profiles, store=store)
    return Draft202012Validator(schema, resolver=resolver)


def errors_of(doc: Any) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)
