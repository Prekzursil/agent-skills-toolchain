#!/usr/bin/env python3
"""Dump receipt_core def + the exact violating rows in wave-2 artifacts."""
import json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
doc = json.loads((REPO / "platform" / "schema" / "receipt.schema.json").read_text(encoding="utf-8"))
defs = doc.get("$defs", {})
rc = defs.get("receipt_core")
print("=== receipt_core $def ===")
print(json.dumps(rc, indent=1)[:9000])
