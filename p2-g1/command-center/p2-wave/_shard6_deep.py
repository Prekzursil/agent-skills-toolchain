#!/usr/bin/env python3
"""Deep-dump BLD-0016 + BLD-0042 + BLD-0035 receipt bodies."""
import json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")

for uid in ("BLD-0016", "BLD-0035", "BLD-0042", "BLD-0033"):
    p = REPO / "command-center/receipts" / f"{uid}.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    print("=" * 40, uid)
    rep = d.get("report") or {}
    print("report.kind:", rep.get("kind"))
    for o in rep.get("observations") or []:
        print("  OBS:", json.dumps(o, ensure_ascii=False)[:500])
    ev = d.get("evidence") or []
    for e in ev[:4]:
        print("  EV:", json.dumps(e, ensure_ascii=False)[:300])
    for t in (d.get("tests") or [])[:2]:
        print("  T keys:", sorted(t.keys()))
    for a in (d.get("artifacts") or [])[:3]:
        print("  ART:", json.dumps(a, ensure_ascii=False)[:220])
    for r in (d.get("residual_unknowns") or [])[:2]:
        print("  RES:", json.dumps(r, ensure_ascii=False)[:260])
