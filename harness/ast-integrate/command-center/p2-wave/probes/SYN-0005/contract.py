"""Load the live SYN-0005 schema.

Catalog ``command-center/schema/decision-trace.schema.json`` is a generated
``$ref`` shim pointing at ``https://ast-integrate.invalid/...``. Distro
jsonschema 4.10 follows that URL and raises RefResolutionError, so garbage
is not rejected as ValidationError and emit crashes. The unit-local Draft-07
file is the discriminating contract the probes actually run.
"""
from __future__ import annotations

import json
from pathlib import Path

LOCAL_REL = "command-center/p2-wave/probes/SYN-0005/decision-trace.schema.json"
CATALOG_REL = "command-center/schema/decision-trace.schema.json"


def is_generated_shim(schema: dict) -> bool:
    ref = str(schema.get("$ref") or "")
    comment = str(schema.get("$comment") or "")
    return "GENERATED SHIM" in comment or "ast-integrate.invalid" in ref


def load_schema(repo: Path) -> dict:
    local = repo / LOCAL_REL
    schema = json.loads(local.read_text(encoding="utf-8"))
    if is_generated_shim(schema):
        raise RuntimeError(f"{LOCAL_REL} must not be a generated shim")
    schema.pop("$id", None)
    return schema
