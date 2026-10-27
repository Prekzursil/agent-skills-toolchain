"""w4s10 reviewer - program-wide green census over all 2007 units (receipt-level)."""
import json, os, sys
from pathlib import Path
G1 = Path(r"C:/Users/Prekzursil/p2-g1")
AI = Path(r"C:/Users/Prekzursil/source/ast-integrate")
sys.path.insert(0, str(AI / "platform/lib"))
os.environ["AST_INTEGRATE_ROOT"] = str(G1)
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
import schema_resolver
DECLARED = "command-center/schema/receipt.schema.json"
validator_cache = {}

cat = json.loads((G1 / "command-center/WORK-UNIT-CATALOG.json").read_bytes().decode("utf-8"))
ids = [u["id"] for u in cat["work_units"]]
print("catalog units:", len(ids))

counts = {"no_receipt": [], "unparseable": [], "schema_error": [], "state_not_success": [],
          "no_independent_pass": [], "green": []}
schema_err_samples = {}
for uid in ids:
    rp = G1 / ("command-center/receipts/" + uid + ".json")
    if not rp.is_file():
        counts["no_receipt"].append(uid); continue
    try:
        r = json.loads(rp.read_bytes().decode("utf-8"))
    except Exception:
        counts["unparseable"].append(uid); continue
    errs = schema_resolver.validate_artifact(r, DECLARED)
    if errs:
        counts["schema_error"].append(uid)
        key = errs[0][:80]
        schema_err_samples.setdefault(key, []).append(uid)
        continue
    if r.get("state") != "SUCCESS":
        counts["state_not_success"].append(uid); continue
    rev = r.get("reviewer") or {}
    if rev.get("verdict") != "PASS" or not rev.get("independent"):
        counts["no_independent_pass"].append(uid); continue
    counts["green"].append(uid)

out = G1 / "_reviewer-w4s10/w4s10-rerun/census.json"
summary = {k: len(v) for k, v in counts.items()}
summary["total"] = len(ids)
(out).write_text(json.dumps({"summary": summary,
                             "schema_error_samples": {k: v[:8] for k, v in schema_err_samples.items()},
                             "lists_first50": {k: v[:50] for k, v in counts.items()}}, indent=1), encoding="utf-8")
print(json.dumps(summary, indent=1))
print("top schema-error classes:")
for k, v in sorted(schema_err_samples.items(), key=lambda kv: -len(kv[1]))[:8]:
    print(" ", len(v), "|", k)
