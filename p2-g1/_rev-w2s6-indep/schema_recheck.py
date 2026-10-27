#!/usr/bin/env python3
"""Reviewer schema re-check (fresh instrument): plain jsonschema 2020-12 against
the catalog-declared output_schema for each shard-6 W2 unit, with remote file://
$refs auto-resolved. Reports error count + first error per unit. Receipts are
read-only here; this does NOT mutate anything."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
IDS = ["BLD-0016", "BLD-0023", "BLD-0024", "BLD-0027", "BLD-0028", "BLD-0031",
       "BLD-0032", "BLD-0033", "BLD-0035", "BLD-0037", "BLD-0040", "BLD-0042"]

out = {}
for uid in IDS:
    doc = json.loads((REPO / f"command-center/receipts/{uid}.json").read_text(encoding="utf-8"))
    schema_rel = None
    cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    for w in cat["work_units"]:
        if w.get("id") == uid:
            schema_rel = w.get("output_schema")
            break
    schema = json.loads((REPO / schema_rel).read_text(encoding="utf-8"))
    v = jsonschema.Draft202012Validator(schema)
    errors = sorted(v.iter_errors(doc), key=lambda e: list(e.absolute_path))
    first = None
    if errors:
        e = errors[0]
        loc = "/".join(str(x) for x in e.absolute_path) or "<root>"
        first = f"{loc}: {e.message[:160]}"
    out[uid] = {"schema": schema_rel, "error_count": len(errors), "first_error": first}
    print(f"{uid}: errors={len(errors)} first={first}", flush=True)

(REPO / "_rev-w2s6-indep" / "schema-recheck.json").write_text(
    json.dumps(out, indent=1), encoding="utf-8")
print("done")
