import json
import warnings
from pathlib import Path

warnings.simplefilter("ignore")
import jsonschema
from jsonschema import RefResolver

REPO = Path("C:/Users/Prekzursil/p2-g1")
UNITS = ["BLD-0001", "BLD-0002", "BLD-0010", "BLD-0016", "BLD-0023", "BLD-0024",
         "BLD-0027", "BLD-0028", "BLD-0037", "BLD-0042"]
SCHEMAS = {
    "BLD-0001": "blindspot-register.schema.json",
    "BLD-0002": "reachability-report.schema.json",
    "BLD-0010": "coverage-matrix.schema.json",
    "BLD-0016": "traceability-matrix.schema.json",
    "BLD-0023": "blindspot-register.schema.json",
    "BLD-0024": "triage-revalidation.schema.json",
    "BLD-0027": "blindspot-register.schema.json",
    "BLD-0028": "detector-control-audit.schema.json",
    "BLD-0037": "contradiction-register.schema.json",
    "BLD-0042": "test-quality-census.schema.json",
}
cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
byid = {u["id"]: u for u in cat["work_units"]}

for uid in UNITS:
    wrapper = REPO / "command-center/schema" / SCHEMAS[uid]
    sd = json.loads(wrapper.read_text(encoding="utf-8"))
    doc = json.loads((REPO / byid[uid]["output_path"].replace("\\", "/")).read_text(encoding="utf-8"))
    resolver = RefResolver(base_uri=wrapper.resolve().as_uri(), referrer=sd)
    v = jsonschema.Draft202012Validator(sd, resolver=resolver)
    errs = sorted(v.iter_errors(doc), key=lambda e: list(e.absolute_path))
    print("===", uid, "| errors:", len(errs))
    for e in errs[:6]:
        loc = "/".join(str(x) for x in e.absolute_path) or "<root>"
        print("   at", loc, "->", str(e.message)[:180])
