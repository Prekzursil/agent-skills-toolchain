"""Offline validator for catalog portability_report (jsonschema 4.10 RefResolver).

command-center/schema/receipt.schema.json is a generated shim whose
$defs/portability_report $ref's https://ast-integrate.invalid/... which is
not a network host. Fetching it would make schema_rejects_garbage a detector
that never constrains. Map those $id values onto platform/schema/ files.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
from jsonschema.exceptions import RefResolutionError

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SHIM = "command-center/schema/receipt.schema.json"
PROFILES = "platform/schema/artifact-class-profiles.schema.json"
RECEIPT = "platform/schema/receipt.schema.json"
FRAGMENT = "#/$defs/portability_report"
DECLARED = SHIM + FRAGMENT


def _load(rel: str) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def _refuse_remote(uri: str):
    raise RefResolutionError(f"offline-registry: refused remote fetch of {uri}")


def validator():
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
    resolver = jsonschema.RefResolver.from_schema(
        shim,
        store=store,
        handlers={"http": _refuse_remote, "https": _refuse_remote},
    )
    schema = {"$ref": str(shim.get("$id")) + FRAGMENT}
    return jsonschema.Draft202012Validator(schema, resolver=resolver)


def errors(doc: object) -> list[str]:
    out: list[str] = []
    try:
        for err in validator().iter_errors(doc):
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            out.append(f"{loc}: {err.message}")
    except RefResolutionError as exc:
        out.append(f"<ref>: {exc}")
    return sorted(out)


def schema_rejects_garbage() -> tuple[bool, int]:
    garbage = [{}, {"totally": "unrelated"}, {"x": "x" * 200}]
    rejected = sum(1 for g in garbage if errors(g))
    return rejected == 3, rejected


def payload(doc: dict) -> dict:
    """Domain fields live under report (receipt_core additionalProperties=false)."""
    if not isinstance(doc, dict):
        return {}
    rep = doc.get("report")
    if isinstance(rep, dict) and rep.get("kind") == "portability_report":
        return rep
    return doc
