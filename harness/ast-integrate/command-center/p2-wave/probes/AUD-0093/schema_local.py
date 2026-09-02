"""Offline validator for command-center/schema/audit-finding.schema.json.

jsonschema 4.10 RefResolver otherwise GETs https://ast-integrate.invalid/
and raises RefResolutionError. Bind those $ids to files already on disk.
Does not rewrite command-center/schema/ (no ADV rebuild circle).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DECLARED = "command-center/schema/audit-finding.schema.json"
_RELATIVE = (
    DECLARED,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def _store() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    store: dict[str, dict[str, Any]] = {}
    shim: dict[str, Any] | None = None
    for rel in _RELATIVE:
        doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
        ident = doc.get("$id")
        if not isinstance(ident, str) or not ident:
            raise SystemExit(f"FAILED:AUD-0093 schema {rel} missing $id")
        store[ident] = doc
        store["https://ast-integrate.invalid/" + rel.replace("\\", "/")] = doc
        if rel == DECLARED:
            shim = doc
    if shim is None:
        raise SystemExit("FAILED:AUD-0093 catalog shim not loaded")
    return shim, store


def validator() -> Draft202012Validator:
    shim, store = _store()
    resolver = RefResolver(base_uri=shim["$id"], referrer=shim, store=store)
    return Draft202012Validator(shim, resolver=resolver)


def error_messages(doc: Any) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)
