import json
import warnings
from pathlib import Path

warnings.simplefilter("ignore")
import jsonschema
from jsonschema import RefResolver

REPO = Path("C:/Users/Prekzursil/p2-g1")
cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
byid = {u["id"]: u for u in cat["work_units"]}

# recent wave-4 receipts from OTHER shards, built Oct 24-26 against the current schema
CONTROLS = ["CNF-0149", "TST-0247", "RES-0158", "IMP-0461"]
for uid in CONTROLS:
    u = byid[uid]
    sf = str(u["output_schema"]).split()[0].replace("\\", "/")
    wrapper = REPO / sf
    if not wrapper.is_file():
        print(uid, "WRAPPER MISSING:", sf)
        continue
    sd = json.loads(wrapper.read_text(encoding="utf-8"))
    doc = json.loads((REPO / str(u["output_path"]).replace("\\", "/")).read_text(encoding="utf-8"))
    resolver = RefResolver(base_uri=wrapper.resolve().as_uri(), referrer=sd)
    errs = list(jsonschema.Draft202012Validator(sd, resolver=resolver).iter_errors(doc))
    print(uid, "| wrapper:", Path(sf).name, "| errors:", len(errs))
    for e in errs[:4]:
        print("   ", "/".join(str(x) for x in e.absolute_path) or "<root>", "->", str(e.message)[:140])
