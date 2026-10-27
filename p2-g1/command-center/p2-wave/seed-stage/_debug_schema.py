#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import p2_jsonschema_hook  # noqa: E402
import jsonschema

print("Draft7", type(jsonschema.Draft7Validator), jsonschema.Draft7Validator.__init__)
print("has registry in init", "registry" in jsonschema.Draft7Validator.__init__.__code__.co_varnames if hasattr(jsonschema.Draft7Validator.__init__, "__code__") else "nocode")

schema_path = Path(os.environ["AST_INTEGRATE_ROOT"]) / "command-center/schema/refutation-record.schema.json"
schema = json.loads(schema_path.read_text(encoding="utf-8"))
print("schema keys", list(schema)[:8], "id", schema.get("$id"), "ref", schema.get("$ref"))
try:
    jsonschema.Draft7Validator.check_schema(schema)
    print("check_schema OK")
except Exception as exc:
    print("check_schema FAIL", type(exc), exc)
try:
    v = jsonschema.Draft7Validator(schema)
    print("validator", type(v), getattr(v, "_registry", None), getattr(v, "registry", None))
    doc = {"unit_id": "ADV-0010", "state": "SUCCESS", "sentinel": "SUCCESS:ADV-0010", "artifacts": []}
    errs = list(v.iter_errors(doc))
    print("iter_errors n", len(errs), "head", [e.message for e in errs[:5]])
except Exception as exc:
    print("validate FAIL", type(exc), exc)

resolver = getattr(jsonschema, "RefResolver", None)
print("RefResolver", resolver)
if resolver is not None:
    print("resolve_from_url", resolver.resolve_from_url)
    print("_remote_cache", getattr(resolver, "_remote_cache", None))
    try:
        r = resolver.from_schema(schema)
        print("from_schema ok", type(r))
        url = "https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json"
        print("resolve_from_url try")
        print(r.resolve_from_url(url) if hasattr(r, "resolve_from_url") else "no method")
    except Exception as exc:
        print("resolver FAIL", type(exc), exc)
