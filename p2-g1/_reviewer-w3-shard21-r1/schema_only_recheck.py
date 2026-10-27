#!/usr/bin/env python3
"""Re-run BOTH schema transports on the live receipts (post T2-transport fix)."""
import json, re, sys
from pathlib import Path
REPO = Path.home() / "p2-g1"
UNITS = ["TST-0151","TST-0155","TST-0158","TST-0161","TST-0162","TST-0163",
         "TST-0164","TST-0165","TST-0166","TST-0168","TST-0169","TST-0171"]
sys.path.insert(0, str(REPO / "platform" / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from schema_resolver import validate_artifact as sr_validate, resolve as sr_resolve
from verify_w3_shard21 import independent_fragment_validator, load_json

cat = load_json(REPO / "command-center/WORK-UNIT-CATALOG.json")
catalog = {u["id"]: u for u in cat["work_units"]}
out = {}
for uid in UNITS:
    u = catalog[uid]
    rec = load_json(REPO / u["output_path"].replace("\\", "/"))
    errs1 = sr_validate(rec, u["output_schema"])
    errs2 = independent_fragment_validator(u["output_schema"], rec)
    rs = sr_resolve(u["output_schema"]).as_dict()
    out[uid] = {
        "t1_count": len(errs1), "t1_first": [e[:260] for e in errs1[:8]],
        "t2_count": len(errs2), "t2_first": [e[:260] for e in errs2[:8]],
        "physical": rs["physical_path"], "fragment": rs["physical_fragment"],
        "class": rs["artifact_class"], "pin": rs["report_kind_pinned"],
        "agree": (len(errs1) == 0) == (len(errs2) == 0),
    }
    print(uid, "T1=", len(errs1), "T2=", len(errs2), "agree=", out[uid]["agree"],
          "class=", rs["artifact_class"], "pin=", rs["report_kind_pinned"], flush=True)
Path(__file__).resolve().parent.joinpath("schema-recheck.json").write_text(
    json.dumps(out, indent=1), encoding="utf-8")
print("WROTE schema-recheck.json")
