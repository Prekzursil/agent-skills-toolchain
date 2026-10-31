#!/usr/bin/env python3
"""Scratch: confirm the 4 schema violations are real constraints, not validator artifacts."""
import json
from pathlib import Path

WS = Path("C:/Users/Prekzursil/p2-g1")

s = json.load(open(WS / "command-center/schema/research-claim-record.schema.json", encoding="utf-8"))
rev = s.get("properties", {}).get("reviewer", {})
print("research-claim-record schema reviewer.additionalProperties =", rev.get("additionalProperties"))
print("  reviewer allowed props:", sorted((rev.get("properties") or {}).keys()))
for uid in ("RES-0112", "RES-0114"):
    a = json.load(open(WS / "command-center/research" / f"{uid}.json", encoding="utf-8"))
    print(f"  {uid} artifact reviewer keys:", sorted(a.get("reviewer", {}).keys()))

m = json.load(open(WS / "command-center/schema/measurement-run.schema.json", encoding="utf-8"))
print("measurement-run schema root.required =", m.get("required"))
print("measurement-run schema root.additionalProperties =", m.get("additionalProperties"))
for uid in ("RES-0128", "RES-0144"):
    p = WS / "command-center/research" / f"{uid}.json"
    if not p.is_file():
        print(f"  {uid}: not at default path, checking catalog")
    a = json.load(open(p, encoding="utf-8"))
    print(f"  {uid} has min_bytes_threshold:", "min_bytes_threshold" in a,
          "| root keys:", sorted(a.keys())[:24])
