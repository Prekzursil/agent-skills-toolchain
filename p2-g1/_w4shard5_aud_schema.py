import json
import warnings
from pathlib import Path

warnings.simplefilter("ignore")
import jsonschema
from jsonschema import RefResolver

REPO = Path("C:/Users/Prekzursil/p2-g1")
for uid, wrapper_name in [("AUD-0084", "audit-finding.schema.json"), ("AUD-0096", "audit-drift.schema.json")]:
    wrapper = REPO / "command-center/schema" / wrapper_name
    sd = json.loads(wrapper.read_text(encoding="utf-8"))
    out_rel = ("command-center/audit/AUD-0084-hardcoded-path-census.json" if uid == "AUD-0084"
               else "command-center/audit/AUD-0096-fresh-profile-harness-baseline.json")
    doc = json.loads((REPO / out_rel).read_text(encoding="utf-8"))
    resolver = RefResolver(base_uri=wrapper.resolve().as_uri(), referrer=sd)
    errs = list(jsonschema.Draft202012Validator(sd, resolver=resolver).iter_errors(doc))
    print("===", uid, "| wrapper:", wrapper_name, "| errors:", len(errs))
    for e in errs[:8]:
        print("   at", "/".join(str(x) for x in e.absolute_path) or "<root>", "->", str(e.message)[:170])
