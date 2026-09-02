#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
sys.path.insert(0, str(REPO / "command-center" / "p2-wave" / "seed-stage"))
import p2_jsonschema_hook  # noqa: E402

sys.path.insert(0, str(REPO / "command-center" / "p2-wave" / "probes" / "ADV-0005"))
import engine as E  # noqa: E402

doc = json.loads((REPO / E.OUTPUT_REL).read_text(encoding="utf-8"))
ok, why = E.validate_schema(doc)
print("ok", ok, "why", why)

import jsonschema

schema = json.loads((REPO / E.SCHEMA_REL).read_text(encoding="utf-8"))
v = jsonschema.Draft7Validator(schema)
errs = list(v.iter_errors(doc))
print("n_errs", len(errs))
for e in errs[:12]:
    print("PATH", list(e.absolute_path), "MSG", e.message)
    print("  instance", type(e.instance).__name__, repr(e.instance)[:180])
