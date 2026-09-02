"""Load the CNL-0058 local design-note schema.

The catalog shim at command-center/schema/council-design-note.schema.json is a
$ref to https://ast-integrate.invalid/... . Draft7Validator follows that $ref
over the network and raises RefResolutionError on this Linux worktree, which
makes every document (including garbage) fail to even be judged. This local
schema is the non-vacuous contract the probes actually run.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
SCHEMA_PATH = HERE / "design-note.schema.json"


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validator() -> jsonschema.Draft7Validator:
    return jsonschema.Draft7Validator(load_schema())
