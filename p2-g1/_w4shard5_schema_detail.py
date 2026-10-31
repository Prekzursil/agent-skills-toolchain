import json
import warnings
from pathlib import Path

warnings.simplefilter("ignore")
import jsonschema
from jsonschema import RefResolver

REPO = Path("C:/Users/Prekzursil/p2-g1")
SCHEMAS = {
    "AUD-0084": "audit-finding.schema.json",
    "AUD-0096": "audit-drift.schema.json",
    "BLD-0001": "blindspot-register.schema.json",
    "BLD-0002": "reachability-report.schema.json",
    "BLD-0010": "coverage-matrix.schema.json",
    "BLD-0016": "traceability-matrix.schema.json",
    "BLD-0023": "blindspot-register.profile" if False else "blindspot-register.schema.json",
    "BLD-0024": "schema-PLACEHOLDER",
    "BLD-0027": "blindspot-register.schema.json",
    "BLD-0028": "detector-control-audit.schema.json",
    "BLD-0037": "contradiction-register.schema.json",
    "BLD-0042": "test-quality-census.schema.json",
}
SCHEMAS["BLD-0024"] = "triage-revalidation.schema.json"

cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
byid = {u["id"]: u for u in cat["work_units"]}
out = {}
for uid, wn in SCHEMAS.items():
    wrapper = REPO / "command-center/schema" / wn
    sd = json.loads(wrapper.read_text(encoding="utf-8"))
    out_rel = str(byid[uid]["output_path"]).replace("\\", "/")
    doc = json.loads((REPO / out_rel).read_text(encoding="utf-8"))
    resolver = RefResolver(base_uri=wrapper.resolve().as_uri(), referrer=sd)
    errs = list(jsonschema.Draft202012Validator(sd, resolver=resolver).iter_errors(doc))
    rows = []
    for e in errs:
        rows.append({
            "at": "/".join(str(x) for x in e.absolute_path) or "<root>",
            "schema_path": "/".join(str(x) for x in e.schema_path)[:200],
            "msg": str(e.message)[:220],
        })
    out[uid] = {
        "output_schema_wrapper": "command-center/schema/" + wn,
        "violation_count": len(rows),
        "violations": rows,
    }
(REPO / "_w4shard5_schema_violations_full.json").write_text(
    json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
print("written; counts:", {k: v["violation_count"] for k, v in out.items()})
