#!/usr/bin/env python3
"""Shard-20 wave-4 builder: full C2 schema-error dump for the 12 TST receipts."""
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

for uid in UNITS:
    p = REPO / "command-center" / "receipts" / (uid + ".json")
    doc = json.loads(p.read_text(encoding="utf-8"))
    errs = gate.validate_receipt(doc)
    print("=" * 20, uid, "errors:", len(errs))
    for e in errs:
        print("   -", e)
