import json, sys
from pathlib import Path
REPO = Path(r"C:\Users\Prekzursil\p2-g1")
cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
units = {u.get("id"): u for u in cat.get("work_units", []) if isinstance(u, dict)}
mine = ["RES-0184","RES-0185","RES-0187","RES-0188","RES-0191","RES-0192","RES-0193","SYN-0003","SYN-0007","SYN-0008","SYN-0035","TST-0005"]
out = {}
for uid in mine:
    u = units.get(uid)
    if u is None:
        print(f"MISSING-CATALOG {uid}")
        continue
    out[uid] = u
    print(f"--- {uid}")
    for k in ("output_path","output_schema","probes","dependencies","completion_sentinel","owner_gate","owner-gated","gate","status"):
        if k in u: print(f"  {k}: {json.dumps(u[k])[:300]}")
    d = str(u.get("description") or u.get("description_text") or "")[:400]
    print(f"  description: {d}")
    print(f"  keys: {sorted(u.keys())}")
(REPO / "_p2shard20-w2" / "entries.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print("saved entries.json")
