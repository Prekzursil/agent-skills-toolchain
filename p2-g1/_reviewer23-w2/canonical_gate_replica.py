#!/usr/bin/env python3
"""Replicate the program's canonical output_schema gate (tools/command-center/
output_schema_gate.py) exactly: jsonschema.validate(payload, whole_schema_file),
schema loaded from the declared output_schema path with the fragment ignored.
This is the binding check the vendor boundary enforces; my earlier pointer-merged
run was stricter than the binding lane. Fail-closed; no writes."""
import json
import sys
from pathlib import Path

import jsonschema

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
UNITS = ["TST-0113", "TST-0124", "TST-0129", "TST-0130", "TST-0136", "TST-0137",
         "TST-0138", "TST-0139", "TST-0141", "TST-0142", "TST-0143", "TST-0144"]

with open(REPO / "command-center" / "catalog-slices" / "TST-1.json", encoding="utf-8") as f:
    cat = {e["id"]: e for e in json.load(f)}

npass = 0
for uid in UNITS:
    e = cat[uid]
    schema_path = REPO / e["output_schema"]
    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)  # whole file, fragment ignored (canonical gate)
    with open(REPO / e["output_path"], encoding="utf-8") as f:
        payload = json.load(f)
    try:
        jsonschema.validate(payload, schema)
        npass += 1
        print("SCHEMA-GATE PASS %s (%s)" % (uid, schema_path.name))
    except jsonschema.ValidationError as exc:
        print("SCHEMA-GATE FAIL %s (%s): %s" % (uid, schema_path.name, exc.message[:220]))
print("CANONICAL GATE: %d/%d PASS" % (npass, len(UNITS)))
