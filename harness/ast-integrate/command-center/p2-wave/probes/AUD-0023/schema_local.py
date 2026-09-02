#!/usr/bin/env python3
"""Disk-only validator for command-center/schema/audit-finding.schema.json.

jsonschema 4.10 RefResolver fetches https $ref by default. The catalog shim
points at ast-integrate.invalid, which is not a network host. This module
loads the physical schemas from disk and never opens a socket.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SHIM = "command-center/schema/audit-finding.schema.json"
PROFILES = "platform/schema/artifact-class-profiles.schema.json"
RECEIPT = "platform/schema/receipt.schema.json"


def _load(rel: str) -> dict[str, Any]:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def validator() -> Draft202012Validator:
    profiles = _load(PROFILES)
    receipt = _load(RECEIPT)
    shim = _load(SHIM)
    store = {
        profiles["$id"]: profiles,
        receipt["$id"]: receipt,
        shim.get("$id") or ("https://ast-integrate.invalid/" + SHIM): shim,
        "https://ast-integrate.invalid/" + SHIM: shim,
        "https://ast-integrate.invalid/" + PROFILES: profiles,
        "https://ast-integrate.invalid/" + RECEIPT: receipt,
    }
    resolver = RefResolver(
        base_uri=str(shim.get("$id") or ""),
        referrer=shim,
        store=store,
    )
    return Draft202012Validator(shim, resolver=resolver)


def errors_of(doc: Any) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)
