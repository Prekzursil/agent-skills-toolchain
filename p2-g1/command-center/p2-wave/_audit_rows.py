"""AUDIT (independent): dump the catalog rows for the 5 claimed-delivered units, verbatim."""

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CAT = json.loads(
    (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
)
by = {u["id"]: u for u in CAT["work_units"]}

for uid in ["IMP-0433", "AUD-0041", "AUD-0051", "AUD-0030", "AUD-0020", "AUD-0001"]:
    u = by.get(uid)
    if u is None:
        print(f"=== {uid}: NOT IN CATALOG ===")
        continue
    print(f"=== {uid} ===")
    for k in (
        "phase",
        "output_path",
        "output_schema",
        "dependencies",
        "owner_approval_required",
        "reviewer_requirement",
        "substrate",
    ):
        print(f"  {k}: {u.get(k)!r}")
    print(f"  ALL KEYS: {sorted(u.keys())}")
