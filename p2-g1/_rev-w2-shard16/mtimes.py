import json, datetime
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
UNITS = ["IMP-0470","IMP-0478","REL-0001","REL-0006","REL-0014","REL-0017",
         "REL-0020","REL-0021","REL-0022","RES-0004","RES-0009","RES-0011"]
cat = json.loads((REPO/"command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
by = {u.get("id"): u for u in cat.get("work_units") or []}
for uid in UNITS:
    out = REPO / by[uid]["output_path"].replace("\\", "/")
    mt = datetime.datetime.fromtimestamp(out.stat().st_mtime, datetime.timezone.utc)
    print(uid, "mtime_utc:", mt.isoformat(timespec="seconds"))
