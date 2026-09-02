#!/usr/bin/env python3
"""shard-01 scratch: print generic_report requirements from receipt.schema.json."""
import json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
doc = json.loads((REPO / "platform/schema/receipt.schema.json").read_text(encoding="utf-8"))
defs = doc.get("$defs") or {}
g = defs.get("generic_report") or {}
print("generic_report keys:", sorted(g.keys()))
print("required:", g.get("required"))
props = g.get("properties") or {}
print("properties:", sorted(props.keys()))
for k in ("evidence", "report", "timestamps", "retry", "negative_controls", "manifest_registration", "downstream_consumers", "residual_unknowns", "defects", "tests", "produced_by"):
    print("---", k, "->", json.dumps(props.get(k))[:500])
