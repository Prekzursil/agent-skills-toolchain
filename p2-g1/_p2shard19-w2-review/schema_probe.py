import json
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
sys.path.insert(0, str(REPO / "platform" / "lib"))
import schema_resolver as sres  # noqa: E402

art = REPO / "command-center/research/evidence-quality/RES-0151-evidence-saturation-stopping-metric.json"
doc = json.loads(art.read_text(encoding="utf-8"))
sch_path = "command-center/schema/measurement-run.schema.json"

# 1) raw schema inspection: what does it require at root?
schema = json.loads((REPO / sch_path).read_text(encoding="utf-8"))
print("schema top keys:", sorted(schema.keys()))
print("root required:", schema.get("required"))
defs = schema.get("$defs") or schema.get("definitions") or {}
print("defs:", list(defs.keys())[:12])
artdef = defs.get("artifact") or {}
print("artifact def:", json.dumps(artdef)[:400])

# 2) which fields does the artifact actually carry?
print()
print("artifact top keys:", sorted(doc.keys()))
print("has downstream_consumers:", "downstream_consumers" in doc)
print("has manifest_registration:", "manifest_registration" in doc)
print("has residual_unknowns:", "residual_unknowns:" in doc or "residual_unknowns" in doc)
print("artifacts rows:", [(a.get("role"), sorted(a.keys())) for a in doc.get("artifacts", [])])

# 3) does the CLOSED control artifact RES-0173 (same schema) pass?
cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
for e in cat["work_units"]:
    if e.get("id") == "RES-0173":
        p = REPO / str(e["output_path"])
        print()
        print("RES-0173 artifact:", p.name, "exists:", p.is_file())
        if p.is_file():
            d2 = json.loads(p.read_text(encoding="utf-8"))
            errs2 = sres.validate_artifact(d2, e["output_schema"])
            print("RES-0173 schema errors:", len(errs2), errs2[:4])
            print("RES-0173 has downstream_consumers:", "downstream_consumers" in d2,
                  "| manifest_registration:", "manifest_registration" in d2)
