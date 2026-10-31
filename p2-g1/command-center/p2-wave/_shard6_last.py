#!/usr/bin/env python3
"""Final ground-truth bits for probe design."""
import json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")

d = json.loads(
    (REPO / "command-center/receipts/BLD-0032.json").read_text(encoding="utf-8")
)
rep = d.get("report") or {}
print("BLD-0032 report keys:", sorted(rep.keys()))
for k in sorted(rep.keys()):
    v = rep[k]
    s = json.dumps(v, ensure_ascii=False)
    print(f"  {k}: {s[:300]}")
ev = d.get("evidence") or []
for e in ev[:6]:
    print("  EV:", json.dumps(e, ensure_ascii=False)[:260])

# live facts
for p in (
    "tools/lib/net-allowlist.mjs",
    "tools/lib",
):
    q = REPO / p
    print(p, "exists=", q.exists())
tl = REPO / "tools/lib"
if tl.is_dir():
    print("  tools/lib files:", [f.name for f in sorted(tl.iterdir())][:12])

tr = json.loads(
    (REPO / "command-center/TEST-REGISTRY.json").read_text(encoding="utf-8")
)
if isinstance(tr, dict):
    print("TEST-REGISTRY keys:", sorted(tr.keys())[:12])
    for k, v in tr.items():
        if isinstance(v, list):
            print(f"  {k}: list len={len(v)} [0]={json.dumps(v[0])[:200] if v else ''}")
            break
elif isinstance(tr, list):
    print("TEST-REGISTRY rows:", len(tr), "[0]:", json.dumps(tr[0])[:220])

d42 = json.loads(
    (REPO / "command-center/receipts/BLD-0042.json").read_text(encoding="utf-8")
)
rep42 = d42["report"]
print("BLD-0042 counts:", json.dumps(rep42["counts"], ensure_ascii=False))
print("BLD-0042 len(finding_register):", len(rep42["finding_register"]))
print("BLD-0042 known_require_complete:", json.dumps(rep42["known_require_complete"])[:400])
