import json, os
from pathlib import Path
REPO = Path("C:/Users/Prekzursil/p2-g1")
cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
units = {u["id"]: u for u in cat.get("work_units", []) if isinstance(u, dict)}

# authoritative shard list from the prior entries extraction
ent_p = REPO / "_shard5_entries.json"
ent = json.loads(ent_p.read_text(encoding="utf-8"))
ids = []
if isinstance(ent, dict):
    for k in ("unit_ids", "units", "ids"):
        if k in ent:
            ids = ent[k]
            break
    if not ids and "work_units" in ent:
        ids = [u["id"] if isinstance(u, dict) else u for u in ent["work_units"]]
elif isinstance(ent, list):
    ids = [u["id"] if isinstance(u, dict) else u for u in ent]
print("SHARD5 ENTRIES LIST:", ids, "n=", len(ids))
for uid in ids:
    u = units.get(uid)
    if u is None:
        print(uid, "NOT-IN-CATALOG")
        continue
    print("---", uid)
    print("  output_path  :", u.get("output_path"))
    print("  output_schema:", u.get("output_schema"))
    print("  probes       :", json.dumps(u.get("probes"))[:400])
    print("  deps         :", json.dumps(u.get("dependencies"))[:200])
