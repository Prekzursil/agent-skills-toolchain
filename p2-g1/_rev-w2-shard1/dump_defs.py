#!/usr/bin/env python3
"""Dump the exploit-proof and benchmark-integrity class $defs structure."""
import json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
doc = json.loads((REPO / "platform" / "schema" / "artifact-class-profiles.schema.json").read_text(encoding="utf-8"))
defs = doc.get("$defs") or {}
print("classes:", sorted(defs))
ep = defs.get("exploit-proof")
print("\n=== exploit-proof $def (first 120 lines pretty) ===")
print(json.dumps(ep, indent=1)[:6000])
bi = defs.get("benchmark-integrity")
print("\n=== benchmark-integrity $def ===")
print(json.dumps(bi, indent=1)[:3500])
