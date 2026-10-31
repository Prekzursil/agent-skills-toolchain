"""Estate-wide receipt admission refresh (w4s0 reporting duty).

Same instrument as _estate_receipt_admission_sweep_w3s11.py (drives
command-center/receipt_validate.admit_path in-process over ALL receipts) but
writes to the w4s0 resume dir; the w3s11 lane's output file is not touched.
Answers the owner's "how close to full 2007 green" with the current numbers.
"""
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path.home() / "p2-g1"
RV = REPO / "command-center" / "receipt_validate.py"
OUT = REPO / "_p2shard0-w4-resume" / "_estate_admission_refresh_w4s0.json"

spec = importlib.util.spec_from_file_location("rv_w4s0", RV)
mod = importlib.util.module_from_spec(spec)
sys.modules["rv_w4s0"] = mod
spec.loader.exec_module(mod)

cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
catalog_ids = [u["id"] for u in cat["work_units"]]
id_set = set(catalog_ids)

rows = []
verdicts = Counter()
state_x_verdict = Counter()
reason_heads = Counter()
accepted_units = set()
success_accept = 0
for p in sorted((REPO / "command-center" / "receipts").glob("*.json")):
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
        state = doc.get("state")
    except Exception:
        doc = None
        state = "UNPARSEABLE"
    verdict, cnums, reasons = mod.admit_path(p)
    verdicts[verdict] += 1
    state_x_verdict["%s|%s" % (state, verdict)] += 1
    if verdict == "ACCEPT":
        accepted_units.add(p.stem)
        if state == "SUCCESS":
            success_accept += 1
    else:
        head = reasons[0][:110] if reasons else "no-reason"
        reason_heads[head] += 1
    rows.append({"unit": p.stem, "state": str(state), "verdict": verdict})

no_receipt = [u for u in catalog_ids if u not in {r["unit"] for r in rows}]
summary = {
    "catalog_work_units": len(catalog_ids),
    "receipt_files": len(rows),
    "units_with_no_registered_receipt": len(no_receipt),
    "verdicts": dict(verdicts),
    "state_x_verdict": dict(state_x_verdict),
    "admitted_units": len(accepted_units),
    "fully_green_units_state_SUCCESS_and_ACCEPT": success_accept,
    "top_reject_reasons": reason_heads.most_common(12),
}
OUT.write_text(json.dumps({"summary": summary, "rows": rows}, indent=1) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=1))
