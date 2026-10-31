"""Extract precise failing condition numbers (ConditionOutcome uses n/outcome/basis)."""
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
    frag = "benchmark_result" if uid in ("TST-0230", "TST-0233") else "security_report"
    errs = g.validate_receipt(doc, fragment=frag)
    blocking = result.blocking_conditions
    out[uid] = {
        "complete": result.complete,
        "marker": result.marker(),
        "blocking_conditions": [
            {"n": c.n, "text": c.text[:120], "outcome": c.outcome, "basis": c.basis[:500]}
            for c in blocking
        ],
        "coherence_extra": [e[:250] for e in extra][:12],
        "schema_error_count": len(errs),
        "schema_errors_first10": [e[:250] for e in errs[:10]],
    }

dest = Path(r"C:/Users/Prekzursil/p2-g1/_reviewer-w3s32-tmp-pred.json")
dest.write_text(json.dumps(out, indent=1), encoding="utf-8")
for uid, row in out.items():
    conds = [f"c{d['n']}:{d['outcome']}" for d in row["blocking_conditions"]]
    print(uid, "| complete:", row["complete"], "| blocking:", conds,
          "| schema_err:", row["schema_error_count"])
