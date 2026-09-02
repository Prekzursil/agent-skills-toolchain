"""Resolve diagram-manifest $ref onto disk (jsonschema 4.10 RefResolver).

The catalog shim $ref's https://ast-integrate.invalid/... which is not a
network host. Fetching it would make schema validation a detector that never
actually constrains. This maps those $id values to platform/schema/ files.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
from jsonschema.exceptions import RefResolutionError

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SHIM = "command-center/schema/diagram-manifest.schema.json"
PROFILES = "platform/schema/artifact-class-profiles.schema.json"
RECEIPT = "platform/schema/receipt.schema.json"


def _load(rel: str) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def _refuse_remote(uri: str):
    raise RefResolutionError(f"offline-registry: refused remote fetch of {uri}")


def validator() -> jsonschema.Draft202012Validator:
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
    return jsonschema.Draft202012Validator(shim, resolver=resolver)


def errors(doc: object) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def garbage_rejected() -> tuple[bool, str]:
    v = validator()
    garbage = (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"unit_id": "SYN-0044", "state": "SUCCESS", "sentinel": "SUCCESS:SYN-0044"},
    )
    for g in garbage:
        if v.is_valid(g):
            return False, f"schema accepted garbage {g!r:.80}"
    return True, "3/3 garbage rejected"
