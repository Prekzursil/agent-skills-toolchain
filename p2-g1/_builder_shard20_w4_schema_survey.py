#!/usr/bin/env python3
"""Shard-20 wave-4: schema envelope requirements + per-receipt field survey (v2)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
UNITS = [
    "TST-0223", "TST-0227", "TST-0230", "TST-0233", "TST-0236", "TST-0238",
    "TST-0243", "TST-0245", "TST-0247", "TST-0249", "TST-0255", "TST-0256",
]

spec = importlib.util.spec_from_file_location(
    "gate", REPO / "platform" / "lib" / "receipt_schema_gate.py"
)
gate = importlib.util.module_from_spec(spec)
sys.modules["gate"] = gate
spec.loader.exec_module(gate)
print("gate SCHEMA_PATH:", gate.SCHEMA_PATH)
schema = gate.load_schema()
defs = schema.get("$defs", {})
core = defs.get("receipt_core") or {}
print("\nreceipt_core required:", core.get("required"))
print("receipt_core additionalProperties:", core.get("additionalProperties"))
print("receipt_core props:", sorted(core.get("properties", {}).keys()))
for name in ("evidence", "tests", "artifacts", "downstream_consumers", "negative_controls",
             "reviewer", "retry", "timestamps", "manifest_registration", "residual_unknowns",
             "spec_anchor", "state", "sentinel", "completion_sentinel", "schema_version",
             "unit_id", "min_bytes_threshold"):
    p = core.get("properties", {}).get(name)
    print("\n---", name, "---")
    print(json.dumps(p, indent=1)[:1500] if p else "ABSENT")

print("\n\nPER-RECEIPT SURVEY")
want = ["schema_version", "unit_id", "id", "state", "sentinel", "completion_sentinel",
        "spec_anchor", "min_bytes_threshold", "retry", "residual_unknowns", "timestamps",
        "manifest_registration", "downstream_consumers", "negative_controls",
        "evidence", "tests", "artifacts", "reviewer"]
print("unit      " + " ".join(w[:7].ljust(7) for w in want))
for uid in UNITS:
    d = json.loads((REPO / "command-center/receipts" / (uid + ".json")).read_text(encoding="utf-8"))
    row = []
    for w in want:
        v = d.get(w)
        ok = "Y" if v not in (None, "", [], {}) else "-"
        row.append(ok.ljust(7))
    print(uid, " ".join(row))
