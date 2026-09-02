"""Resolve repro-report $ref onto disk (jsonschema 4.10 RefResolver).

The catalog shim $ref's https://ast-integrate.invalid/... which is not a
network host. Fetching it would make schema_rejects_garbage a detector that
never actually constrains. This module maps those $id values to the physical
files under platform/schema/, matching CNF-0061/schema_local.py.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
from jsonschema.exceptions import RefResolutionError

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SHIM = "command-center/schema/repro-report.schema.json"
PROFILES = "platform/schema/artifact-class-profiles.schema.json"
RECEIPT = "platform/schema/receipt.schema.json"


def _load(rel: str) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def _refuse_remote(uri: str):
    raise RefResolutionError(f"offline-registry: refused remote fetch of {uri}")


def validator() -> jsonschema.Draft7Validator:
    shim = _load(SHIM)
    profiles = _load(PROFILES)
    receipt = _load(RECEIPT)
    store = {
        shim["$id"]: shim,
        profiles["$id"]: profiles,
        receipt["$id"]: receipt,
    }
    resolver = jsonschema.RefResolver.from_schema(
        shim,
        store=store,
        handlers={"http": _refuse_remote, "https": _refuse_remote},
    )
    # Shim is $ref-only. Probes read validator.schema["properties"]["state"]["enum"].
    shim = dict(shim)
    term = (receipt.get("$defs") or {}).get("terminal_state") or {}
    enum = term.get("enum") or [
        "SUCCESS",
        "FAILED",
        "BLOCKED",
        "SEVERED",
        "TIMEOUT",
        "SUPERSEDED",
        "DROPPED-BY-OWNER",
    ]
    props = dict(shim.get("properties") or {})
    props["state"] = {"type": "string", "enum": list(enum)}
    shim["properties"] = props
    return jsonschema.Draft7Validator(shim, resolver=resolver)


def errors(doc: object) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)
