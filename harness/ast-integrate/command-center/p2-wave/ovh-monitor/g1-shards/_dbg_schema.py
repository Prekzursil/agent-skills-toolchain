#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

root = Path(os.environ.get("AST_INTEGRATE_ROOT") or "/home/prekzursil/p2-g1")
hook_dir = root / "command-center" / "p2-wave" / "seed-stage"
sys.path.insert(0, str(hook_dir))
print("hook_dir", hook_dir, "hook_py", (hook_dir / "p2_jsonschema_hook.py").stat().st_size)
import p2_jsonschema_hook as H  # noqa: E402
import jsonschema  # noqa: E402
print("imported", getattr(H, "__file__", None), "ver", getattr(H, "HOOK_VERSION", None))
print("has _local", hasattr(H, "_local_schema_uri"), "dir", [a for a in dir(H) if "uri" in a.lower() or "retriev" in a.lower() or "HOOK" in a])

profiles = root / "platform" / "schema" / "artifact-class-profiles.schema.json"
doc = json.loads(profiles.read_bytes().decode("utf-8"))
defs = doc.get("$defs") or {}
print("bytes", profiles.stat().st_size, "n_defs", len(defs), "has_synth", "synthesis-candidate" in defs)
print("id", doc.get("$id"))

uri = (
    "file:///C:/Users/Prekzursil/source/ast-integrate/platform/schema/"
    "artifact-class-profiles.schema.json#/$defs/synthesis-candidate"
)
if hasattr(H, "_local_schema_uri"):
    print("local", H._local_schema_uri(uri))
    path = H._uri_to_path(uri)
    print("path", path, "exists", path.is_file())
    got = H._retrieve_contents(uri)
    defs2 = got.get("$defs") or {}
    print("retrieved n_defs", len(defs2), "has_synth", "synthesis-candidate" in defs2)
else:
    print("OLD HOOK - no _local_schema_uri")
    print("hook file head:")
    print((hook_dir / "p2_jsonschema_hook.py").read_text(encoding="utf-8")[:400])

schema_path = root / "command-center" / "schema" / "synthesis-candidate.schema.json"
schema = json.loads(schema_path.read_bytes().decode("utf-8"))
print("shim id", schema.get("$id"), "ref", schema.get("$ref"))
try:
    jsonschema.Draft7Validator.check_schema(schema)
    print("check_schema OK")
except Exception as exc:
    print("check_schema FAIL", type(exc).__name__, exc)
try:
    v = jsonschema.Draft7Validator(schema)
    errs = list(v.iter_errors({"unit_id": "SYN-0009", "state": "SUCCESS", "sentinel": "SUCCESS:SYN-0009"}))
    print("iter_errors", len(errs), [e.message for e in errs[:3]])
except Exception as exc:
    print("validate FAIL", type(exc).__name__, exc)
