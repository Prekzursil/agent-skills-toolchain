#!/usr/bin/env python3
"""Exact errors for ADV-0037 / ADV-0117 (defects-path) + defect/reviewer $defs."""
import json
from pathlib import Path

import jsonschema

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
wu = {x["id"]: x for x in cat["work_units"]}
doc = json.loads((REPO / "platform" / "schema" / "receipt.schema.json").read_text(encoding="utf-8"))
defs = doc.get("$defs") or {}
for key in ("defect", "reviewer", "test_result", "artifact", "downstream_consumer"):
    print(f"=== $defs/{key} ===")
    print(json.dumps(defs.get(key), indent=1)[:2200])
    print()

wrapper = {"allOf": [{"$ref": "#/$defs/generic_report"}], "$defs": defs}
v = jsonschema.validators.validator_for(wrapper)(wrapper)
for uid in ("ADV-0037", "ADV-0117"):
    art = json.loads((REPO / wu[uid]["output_path"]).read_text(encoding="utf-8"))
    print(f"=== {uid} full error list ({'state=' + str(art.get('state'))}) ===")
    for e in v.iter_errors(art):
        print(f"  - {'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message[:260]}")
