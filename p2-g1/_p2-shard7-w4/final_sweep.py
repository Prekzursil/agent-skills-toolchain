import json
from pathlib import Path
REPO = Path(".")
MINE = ['CNF-0149','CNF-0152','CNF-0164','CNF-0167','CNF-0169','CNF-0171','CNF-0172','CNF-0177','CNF-0184','CNF-0188','CNF-0191','CNL-0078']
with open(REPO/"command-center"/"WORK-UNIT-CATALOG.json", encoding="utf-8") as f:
    cat = json.load(f)
units = {u["id"]: u for u in cat["work_units"] if u["id"] in MINE}
print("owner_approval_required per unit:")
for uid in MINE:
    print(" ", uid, units[uid].get("owner_approval_required"))
print()
for uid in ["CNF-0177","CNF-0188","CNL-0078"]:
    p = Path(units[uid]["output_path"])
    with open(p, encoding="utf-8") as f:
        d = json.load(f)
    print(uid, "| claim_verdict:", d.get("claim_verdict"), "| all_numeric_floors_hold:", d.get("all_numeric_floors_hold"), "| state:", d.get("state"))
    rv = d.get("reviewer")
    if isinstance(rv, dict):
        print("   reviewer:", rv.get("verdict"), "independent=", rv.get("independent"))
    # honest verdict recorded?
    for k in ("verdict","claim_under_test","question"):
        if d.get(k) is not None and not isinstance(d.get(k), dict):
            v = str(d.get(k))
            print("  ", k, "=", v[:100])
