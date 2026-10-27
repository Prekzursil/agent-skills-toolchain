import json

d = json.load(open("C:/Users/Prekzursil/source/ast-integrate/platform/schema/artifact-class-profiles.schema.json", encoding="utf-8"))
defs = d["$defs"]
for cls in ("research-claim-record", "measurement-run"):
    df = defs[cls]
    inline = df["allOf"][1]
    print("====", cls, "inline properties:", sorted(inline.get("properties", {}).keys()))
    rev = inline.get("properties", {}).get("reviewer", {})
    print("  inline reviewer ap:", rev.get("additionalProperties"), "allowed:", sorted((rev.get("properties") or {}).keys()))

r = json.load(open("C:/Users/Prekzursil/source/ast-integrate/platform/schema/receipt.schema.json", encoding="utf-8"))
gr = r["$defs"]["generic_report"]
print("==== generic_report keys:", sorted(gr.keys()))
print("  root required:", gr.get("required"))
print("  root additionalProperties:", gr.get("additionalProperties"))
rev = gr.get("properties", {}).get("reviewer", {})
print("  reviewer ap:", rev.get("additionalProperties"), "allowed:", sorted((rev.get("properties") or {}).keys()))
# hunt min_bytes_threshold anywhere
txt = json.dumps(r)
print("  min_bytes_threshold in receipt.schema.json:", "min_bytes_threshold" in txt)
txt2 = json.dumps(d)
print("  min_bytes_threshold in artifact-class-profiles:", "min_bytes_threshold" in txt2)
