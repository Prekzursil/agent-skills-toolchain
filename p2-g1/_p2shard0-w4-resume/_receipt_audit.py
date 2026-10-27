"""Audit the 12 w4s0 registered receipts: admission codes + reviewer state."""
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path.home() / "p2-g1"
RV = REPO / "command-center" / "receipt_validate.py"
spec = importlib.util.spec_from_file_location("rv_audit", RV)
mod = importlib.util.module_from_spec(spec)
sys.modules["rv_audit"] = mod
spec.loader.exec_module(mod)

UNITS = ["ADV-0038","ADV-0040","ADV-0090","ADV-0091","ADV-0096","ADV-0100",
         "ADV-0109","ADV-0110","ADV-0117","ADV-0119","ADV-0123","ADV-0124"]
out = {}
for uid in UNITS:
    p = REPO / "command-center" / "receipts" / (uid + ".json")
    row = {"receipt_exists": p.is_file()}
    if p.is_file():
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            doc = None
            row["parse"] = type(e).__name__
        if doc is not None:
            row["state"] = doc.get("state")
            rev = doc.get("reviewer") or {}
            row["reviewer_verdict"] = rev.get("verdict")
            row["reviewer_independent"] = rev.get("independent")
            row["reviewer_id"] = str(rev.get("reviewer_id"))[:60]
            row["reviewed_at"] = rev.get("reviewed_at")
            row["has_completion_sentinel"] = bool(
                isinstance(doc.get("completion_sentinel"), str) and doc.get("completion_sentinel").strip()
            )
            verdict, codes, reasons = mod.admit_path(p)
            row["admission"] = verdict
            row["codes"] = codes
            row["reasons"] = [r[:110] for r in reasons]
    out[uid] = row
dest = REPO / "_p2shard0-w4-resume/_receipt_audit.json"
dest.write_text(json.dumps(out, indent=1), encoding="utf-8")
for uid, r in out.items():
    line = uid + " " + str(r.get("state")) + "/" + str(r.get("admission"))
    if r.get("codes"):
        line += " codes=" + ",".join(r["codes"])
    line += " rev=" + str(r.get("reviewer_verdict")) + "/ind=" + str(r.get("reviewer_independent"))
    print(line)
