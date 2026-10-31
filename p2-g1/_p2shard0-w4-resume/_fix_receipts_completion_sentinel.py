"""w4s0 resume: repair the registered receipts' admission defect.

All 12 shard units' receipts in command-center/receipts/ REJECT admission on
exactly one code: "C2 missing completion_sentinel". The field is mechanically
derivable from the catalog SSOT (canonical precedent: ACCEPT'd ADV-0005
carries completion_sentinel == catalog completion_sentinel verbatim). This
repair sets ONLY that field; state, reviewer verdicts and every other field
are untouched. 8 BLOCKED receipts stay BLOCKED (builder may not self-close);
4 reviewer-closed SUCCESS receipts keep their closure.
"""
import json
from pathlib import Path

REPO = Path.home() / "p2-g1"
UNITS = ["ADV-0038","ADV-0040","ADV-0090","ADV-0091","ADV-0096","ADV-0100",
         "ADV-0109","ADV-0110","ADV-0117","ADV-0119","ADV-0123","ADV-0124"]

cat = json.load(open(REPO / "command-center/WORK-UNIT-CATALOG.json", encoding="utf-8"))
wu = {x["id"]: x for x in cat["work_units"]}

for uid in UNITS:
    p = REPO / "command-center/receipts" / (uid + ".json")
    doc = json.loads(p.read_text(encoding="utf-8"))
    before_state = doc.get("state")
    if doc.get("completion_sentinel"):
        print(uid, "ALREADY-SET")
        continue
    doc["completion_sentinel"] = wu[uid]["completion_sentinel"]
    p.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(uid, "repaired; state", before_state, "->", doc.get("state"))
print("SUCCESS:12-receipt-sentinel-repair")
