import json, os
from pathlib import Path
repo = Path.home() / "p2-g1"
cat = json.loads((repo / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
units = {u.get("id"): u for u in cat.get("work_units", [])}
print("total units:", len(units))
mine = ["ADV-0037","ADV-0038","ADV-0040","ADV-0090","ADV-0091","ADV-0096","ADV-0100","ADV-0109","ADV-0110","ADV-0117","ADV-0119","ADV-0123"]
missing = [u for u in mine if u not in units]
print("missing from catalog:", missing)
for uid in mine:
    u = units.get(uid)
    if not u:
        continue
    print("=" * 20, uid, "=" * 20)
    for k, v in u.items():
        s = json.dumps(v, ensure_ascii=False)
        if len(s) > 1200:
            s = s[:1200] + " ...TRUNCATED..."
        print(f"[{k}] {s}")
