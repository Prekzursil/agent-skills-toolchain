#!/usr/bin/env python3
"""Summarize the 8 receipts needing probe infrastructure."""
import json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
UIDS = [
    "BLD-0016", "BLD-0027", "BLD-0028", "BLD-0032",
    "BLD-0033", "BLD-0035", "BLD-0040", "BLD-0042",
]

for uid in UIDS:
    p = REPO / "command-center/receipts" / f"{uid}.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    print("=" * 20, uid)
    for k in ("unit_id", "state", "sentinel", "schema_version", "min_bytes_threshold",
              "spec_anchor"):
        if k in d:
            print(f"  {k}: {d[k]}")
    rep = d.get("report") or {}
    print("  report.kind:", rep.get("kind"))
    obs = rep.get("observations") or []
    print("  report.observations:", len(obs), "->", [o.get("name") for o in obs][:12])
    for key in ("artifacts", "evidence", "tests", "negative_controls"):
        v = d.get(key) or []
        print(f"  {key}: len={len(v)}")
        if v and key in ("tests", "negative_controls"):
            first = v[0]
            print(f"    [0]: {json.dumps(first, ensure_ascii=False)[:240]}")
        if v and key == "artifacts":
            print(f"    [0]: {json.dumps(v[0], ensure_ascii=False)[:200]}")
    for k in ("produced_by", "timestamps", "residual_unknowns"):
        v = d.get(k)
        if isinstance(v, dict):
            print(f"  {k}: {json.dumps(v, ensure_ascii=False)[:200]}")
        elif isinstance(v, list):
            print(f"  {k}: len={len(v)} [0]={json.dumps(v[0], ensure_ascii=False)[:180] if v else '[]'}")
    ext = d.get("extensions") or {}
    print("  extensions keys:", sorted(ext.keys())[:25])
