#!/usr/bin/env python3
"""Dump BLD-0016 receipt top-level structure."""
import json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
d = json.loads(
    (REPO / "command-center/receipts/BLD-0016.json").read_text(encoding="utf-8")
)
print("TOP KEYS:", sorted(d.keys()))
for k in sorted(d.keys()):
    v = d[k]
    if isinstance(v, dict):
        print(f"  {k}: dict keys={sorted(v.keys())[:15]}")
    elif isinstance(v, list):
        print(f"  {k}: list len={len(v)}")
        if v:
            print(f"    [0]: {json.dumps(v[0], ensure_ascii=False)[:400]}")
    else:
        s = str(v)
        print(f"  {k}: {s[:200]}")
