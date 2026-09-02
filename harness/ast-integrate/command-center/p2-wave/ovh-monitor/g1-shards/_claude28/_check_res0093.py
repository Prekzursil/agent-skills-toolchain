#!/usr/bin/env python3
"""shard-01 scratch: validate RES-0093 artifact + compare register with live engine."""
import json
import sys
from pathlib import Path

import jsonschema

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
sys.path.insert(0, str(REPO / "command-center" / "p2-wave" / "probes" / "RES-0093"))
import engine as E  # noqa: E402

ART = REPO / "command-center/research/RES-0093.json"
SCHEMA = REPO / "command-center/schema/research-registry.schema.json"
doc = json.loads(ART.read_text(encoding="utf-8"))
schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
v = jsonschema.Draft202012Validator(schema) if "$schema" in schema and "2020" in str(schema.get("$schema")) else jsonschema.Draft7Validator(schema)
errs = ["/".join(str(p) for p in e.absolute_path) + ": " + e.message[:160] for e in v.iter_errors(doc)]
print("schema errors:", len(errs))
for e in errs[:10]:
    print(" ", e)

live_rows = E.build_register()
stored = doc.get("benchmark_register") or []
print("stored rows:", len(stored), "live rows:", len(live_rows))
live_by = {r["benchmark_id"]: r for r in live_rows}
stored_by = {r["benchmark_id"]: r for r in stored}
print("id sets equal:", set(live_by) == set(stored_by))
drift = []
for bid in set(live_by) & set(stored_by):
    l, g = live_by[bid], stored_by[bid]
    for k in ("applicability_verdict", "named_detectable_improvement", "evidence_tier"):
        if g.get(k) != l[k]:
            drift.append((bid, k))
print("field drift:", drift[:10])
print("has tests:", bool(doc.get("tests")), "report:", doc.get("report"))
