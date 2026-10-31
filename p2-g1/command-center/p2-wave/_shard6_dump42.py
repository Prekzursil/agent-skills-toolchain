#!/usr/bin/env python3
"""Dump BLD-0042 report shape + findings."""
import json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
d = json.loads(
    (REPO / "command-center/receipts/BLD-0042.json").read_text(encoding="utf-8")
)
rep = d.get("report") or {}
print("report keys:", sorted(rep.keys()))
for k in sorted(rep.keys()):
    v = rep[k]
    if isinstance(v, dict):
        print(f"  {k}: dict keys={sorted(v.keys())[:18]}")
    elif isinstance(v, list):
        print(f"  {k}: list len={len(v)}")
        if v:
            print(f"    [0]: {json.dumps(v[0], ensure_ascii=False)[:360]}")
    else:
        print(f"  {k}: {str(v)[:240]}")
print()
print("findings-ish top keys:", [k for k in d.keys() if "find" in k.lower() or "cens" in k.lower()])
