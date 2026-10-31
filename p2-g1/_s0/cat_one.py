import json, sys
from pathlib import Path
REPO = Path.home() / "p2-g1"
cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
uid = sys.argv[1]
u = next(x for x in cat["work_units"] if x.get("id") == uid)
print(json.dumps(u, indent=1)[:6000])
