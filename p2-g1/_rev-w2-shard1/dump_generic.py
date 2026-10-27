#!/usr/bin/env python3
"""Dump generic_report requirements vs the wave-2 artifact shapes."""
import json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
doc = json.loads((REPO / "platform" / "schema" / "receipt.schema.json").read_text(encoding="utf-8"))
gr = doc["$defs"]["generic_report"]
print("=== generic_report ===")
print(json.dumps(gr, indent=1)[:8000])
