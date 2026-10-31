#!/usr/bin/env python3
"""Full untruncated schema errors for ADV-0037 / ADV-0117 (defects/consumers)."""
import json
from pathlib import Path

import jsonschema

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
wu = {x["id"]: x for x in cat["work_units"]}
doc = json.loads((REPO / "platform" / "schema" / "receipt.schema.json").read_text(encoding="utf-8"))
defs = doc.get("$defs") or {}
wrapper = {"allOf": [{"$ref": "#/$defs/generic_report"}], "$defs": defs}
v = jsonschema.validators.validator_for(wrapper)(wrapper)
for uid in ("ADV-0037", "ADV-0117"):
    art = json.loads((REPO / wu[uid]["output_path"]).read_text(encoding="utf-8"))
    print(f"=== {uid} state={art.get('state')} ===")
    for e in v.iter_errors(art):
        print(f"PATH {'/'.join(map(str, e.absolute_path)) or '<root>'}")
        print(f"MSG  {e.message}")
        print()
