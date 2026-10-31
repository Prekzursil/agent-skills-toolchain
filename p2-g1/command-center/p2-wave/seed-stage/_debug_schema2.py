#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p2_jsonschema_hook as h
import jsonschema

print("hook file", getattr(h, "__file__", None), "LOADED", h._LOADED, "VER", getattr(h, "HOOK_VERSION", None))
print("Draft7 init", jsonschema.Draft7Validator.__init__)
print("post", getattr(jsonschema.Draft7Validator, "__attrs_post_init__", None))

uri = "https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json"
doc = h._retrieve_contents(uri)
defs = doc.get("$defs") or {}
print("retrieve id", doc.get("$id"))
print("defs n", len(defs), "has refutation-record", "refutation-record" in defs)

schema = json.loads(
    (Path(os.environ["AST_INTEGRATE_ROOT"]) / "command-center/schema/refutation-record.schema.json").read_text(encoding="utf-8")
)
calls: list[str] = []
orig = None

# wrap retrieve by building a validator and seeing errors
v = jsonschema.Draft7Validator(schema)
print("validator type", type(v))
print("registry", v._registry, type(v._registry), type(v._registry).mro())
print("gor", type(v._registry).get_or_retrieve)
try:
    print("retrieve attr", v._registry._retrieve)
except Exception as exc:
    print("no _retrieve", exc)

instance = {"unit_id": "ADV-0010", "state": "SUCCESS", "sentinel": "SUCCESS:ADV-0010"}
try:
    errs = list(v.iter_errors(instance))
    print("errs", len(errs), [e.message for e in errs[:8]])
except Exception as exc:
    print("EXC", type(exc).__name__, exc)

# try Draft202012 which matches the schema $schema
from jsonschema import Draft202012Validator
v2 = Draft202012Validator(schema)
print("d2020 registry", v2._registry)
try:
    errs = list(v2.iter_errors(instance))
    print("d2020 errs", len(errs), [e.message for e in errs[:8]])
except Exception as exc:
    print("d2020 EXC", type(exc).__name__, exc)
