"""Resolve research-registry $ref onto disk (jsonschema 4.10 RefResolver).

The catalog shim $ref's https://ast-integrate.invalid/... which is not a
network host. Fetching it would make schema_rejects_garbage a detector that
never actually constrains. Map those $id values to platform/schema/ files.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
from jsonschema.exceptions import RefResolutionError

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SHIM = "command-center/schema/research-registry.schema.json"
PROFILES = "platform/schema/artifact-class-profiles.schema.json"
RECEIPT = "platform/schema/receipt.schema.json"


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
    return jsonschema.Draft202012Validator(shim, resolver=resolver)


def errors(doc: object) -> list[str]:
    out: list[str] = []
    try:
        for err in validator().iter_errors(doc):
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            out.append(f"{loc}: {err.message}")
    except RefResolutionError as exc:
        out.append(f"<ref>: {exc}")
    return sorted(out)


def schema_rejects_garbage() -> bool:
    garbage = [{}, {"totally": "unrelated", "passing_tests": 999999}, {"x": "x" * 2000}]
    return all(errors(g) for g in garbage)


def domain(doc: dict) -> dict:
    """Census fields live under report (receipt_core additionalProperties=false)."""
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    if isinstance(report.get("servers"), list):
        return report
    return doc
