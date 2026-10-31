"""Extract precise failing condition numbers/messages per unit from the
program's own 12-condition predicate (layer 2) + schema errors (layer 1)."""
import json
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
sys.path.insert(0, str(REPO / "platform" / "lib"))
import receipt_schema_gate as g

uids = ["TST-0206", "TST-0215", "TST-0219", "TST-0221",
        "TST-0223", "TST-0227", "TST-0230", "TST-0233"]

out = {}
for uid in uids:
    doc = json.loads((REPO / "command-center" / "receipts" / f"{uid}.json").read_bytes())
    result, extra = g.evaluate_full(doc, repo_root=REPO, verify_filesystem=False)
    conds = result.conditions
    failing = []
    for c in conds:
        passed = getattr(c, "passed", None)
        if passed is False:
            failing.append({
                "condition": getattr(c, "number", None),
                "title": getattr(c, "title", "")[:90],
                "basis": str(getattr(c, "basis", ""))[:400],
            })
        elif passed is None:
            failing.append({
                "condition": getattr(c, "number", None),
                "title": getattr(c, "title", "")[:90],
                "basis": "NOT-CHECKED: " + str(getattr(c, "basis", ""))[:200],
            })
    # schema errors against the catalog fragment (layer 1, fragment-aware)
    frag = None
    if uid not in ("TST-0230", "TST-0233"):
        frag = "security_report"
    else:
        frag = "benchmark_result"
    errs = g.validate_receipt(doc, fragment=frag)
    out[uid] = {
        "complete": result.complete,
        "failing_conditions": failing,
        "coherence_extra": [e[:200] for e in extra][:10],
        "schema_error_count": len(errs),
        "schema_errors_first10": [e[:200] for e in errs[:10]],
    }

dest = Path(r"C:/Users/Prekzursil/p2-g1/_reviewer-w3s24-r2/predicate_results.json")
dest.write_text(json.dumps(out, indent=1), encoding="utf-8")
for uid, row in out.items():
    conds = [f["condition"] for f in row["failing_conditions"]]
    print(uid, "| complete:", row["complete"],
          "| failing conditions:", conds,
          "| schema errors:", row["schema_error_count"])
