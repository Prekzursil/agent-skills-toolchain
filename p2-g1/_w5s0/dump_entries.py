import json, sys
from pathlib import Path
REPO = Path(r"C:\Users\Prekzursil\p2-g1")
cat = json.loads((REPO/"command-center"/"WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
units = cat.get("work_units") or []
print("total units:", len(units))
MINE = ["ADV-0038","ADV-0040","ADV-0090","ADV-0091","ADV-0096","ADV-0100","ADV-0109","ADV-0110","ADV-0117","ADV-0119","ADV-0123","ADV-0124"]
out = {}
for u in units:
    if isinstance(u, dict) and u.get("id") in MINE:
        out[u["id"]] = u
print("found:", sorted(out.keys()))
missing = [m for m in MINE if m not in out]
print("missing from catalog:", missing)
(REPO/"_w5s0"/"entries.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
for uid in MINE:
    u = out.get(uid)
    if not u:
        continue
    print("="*80)
    print(uid)
    print(json.dumps(u, indent=1, ensure_ascii=False)[:3000])
