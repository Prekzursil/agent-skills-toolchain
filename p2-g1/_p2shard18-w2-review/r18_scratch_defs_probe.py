import json

p = "C:/Users/Prekzursil/source/ast-integrate/platform/schema/artifact-class-profiles.schema.json"
d = json.load(open(p, encoding="utf-8"))
defs = d["$defs"]
for cls in ("research-claim-record", "measurement-run"):
    df = defs[cls]
    print(cls, "def keys:", sorted(df.keys()))
    props = df.get("properties", {})
    rev = props.get("reviewer", {})
    print("  reviewer additionalProperties:", rev.get("additionalProperties"))
    print("  reviewer allowed:", sorted((rev.get("properties") or {}).keys()))
    print("  root required:", df.get("required"))
    print("  root additionalProperties:", df.get("additionalProperties"))
