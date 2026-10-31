#!/usr/bin/env python3
import importlib.util, json, sys, io
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
REPO = Path(r"C:/Users/Prekzursil/p2-g1")
GATE = REPO / "platform/lib/receipt_schema_gate.py"
spec = importlib.util.spec_from_file_location("rsg", GATE)
mod = importlib.util.module_from_spec(spec)
sys.modules["rsg"] = mod
spec.loader.exec_module(mod)

cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
byid = {u.get("id"): u for u in cat["work_units"]}
MY12 = ["ADV-0005","ADV-0010","ADV-0014","ADV-0015","ADV-0018","ADV-0019",
        "ADV-0022","ADV-0023","ADV-0024","ADV-0028","ADV-0029","ADV-0037"]
for uid in MY12:
    rp = REPO / ("command-center/receipts/" + uid + ".json")
    r = json.loads(rp.read_text(encoding="utf-8"))
    frag_src = byid[uid].get("output_schema") or ""
    base, frag = mod.parse_schema_ref(frag_src)
    res = mod.evaluate_gate_a(r, repo_root=str(REPO), verify_filesystem=True)
    blocking = [(c.n, c.outcome) for c in res.blocking_conditions]
    print(uid, "| frag:", frag, "| schema_errors:", len(res.schema_errors),
          "| complete:", res.complete, "| blocking:", blocking[:6])
    if res.schema_errors:
        for e in res.schema_errors[:4]:
            print("    SE:", e[:160])
