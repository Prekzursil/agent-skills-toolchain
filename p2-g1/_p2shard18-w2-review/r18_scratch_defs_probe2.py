import json

p = "C:/Users/Prekzursil/source/ast-integrate/platform/schema control plane"
d = json.load(open("C:/Users/Prekzursil/source/ast-integrate/platform/schema/artifact-class-profiles.schema.json", encoding="utf-8"))
defs = d["$defs"]
for cls in ("research-claim-record", "measurement-run"):
    df = defs[cls]
    print(cls, "-> allOf branches:", len(df["allOf"]))
    for i, br in enumerate(df["allOf"]):
        ref = br.get("$ref", "")
        keys = sorted(br.keys())
        print(f"  [{i}] keys={keys} ref={ref}")
