"""BUILD lane probe: list the SATISFIABLE units with their output_path + quoted requirement."""

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
vs = json.loads(
    (ROOT / "command-center/p2-next/VENDOR-SATISFIABILITY.json").read_text(
        encoding="utf-8"
    )
)
cat = json.loads(
    (ROOT / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
)
by_id = {u["id"]: u for u in cat["work_units"]}

sat = [u for u in vs["units"] if u["verdict"] == "SATISFIABLE_NOW"]
rail = [u for u in vs["units"] if u["verdict"] == "RAIL_BLOCKED"]
print(f"SATISFIABLE={len(sat)}  RAIL_BLOCKED={len(rail)}")
print()
for u in sat:
    cu = by_id.get(u["id"], {})
    print("=" * 100)
    print(f"{u['id']}  reviewer_vendor={u['reviewer_vendor']}  rule={u['rule']}")
    print(f"  output_path: {cu.get('output_path')}")
    print(f"  title      : {cu.get('title')}")
    req = cu.get("reviewer_requirement") or "(none in catalog)"
    print(f"  REQUIREMENT: {req}")
    for k in ("blocked_on", "receipt_blocked_on", "notes"):
        if u.get(k):
            print(f"  {k}: {u[k]}")
print()
print("RAIL-BLOCKED IDS (%d):" % len(rail))
print("  " + " ".join(sorted(x["id"] for x in rail)))
