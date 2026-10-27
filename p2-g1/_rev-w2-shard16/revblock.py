import json
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
UNITS = ["IMP-0470","IMP-0478","REL-0001","REL-0006","REL-0014","REL-0017",
         "REL-0020","REL-0021","REL-0022","RES-0004","RES-0009","RES-0011"]
cat = json.loads((REPO/"command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
by = {u.get("id"): u for u in cat.get("work_units") or []}

for uid in UNITS:
    u = by[uid]
    doc = json.loads((REPO / u["output_path"].replace("\\", "/")).read_text(encoding="utf-8"))
    rev = doc.get("reviewer") or {}
    # independence: reviewer vendor must differ from the unit's assigned builder vendor
    av = ((u.get("assigned_model_vendor_role") or {}).get("vendor") or "").lower()
    rv = str(rev.get("vendor") or "").lower()
    same = (rv == av) if (rv and av) else None
    print(uid,
          "| reviewer_id_set:", bool(rev.get("reviewer_id")),
          "| rv_len:", len(str(rev.get("reviewer_id") or "")),
          "| verdict_is_PASS:", rev.get("verdict") == "PASS",
          "| independent_is_True:", rev.get("independent") is True,
          "| fresh_ctx:", rev.get("fresh_context"),
          "| vendor_same_as_builder:", same,
          "| reviewed_at:", rev.get("reviewed_at") or "-")
    print("    failure_present:", isinstance(doc.get("failure"), dict))
    print("    reviewer_id head:", str(rev.get("reviewer_id") or "")[:90])
