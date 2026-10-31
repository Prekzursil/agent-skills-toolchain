import json
CAT = r"C:\Users\Prekzursil\p2-g1\command-center\WORK-UNIT-CATALOG.json"
with open(CAT, "r", encoding="utf-8") as f:
    cat = json.load(f)
wu = cat.get("work_units", {})
print("work_units type:", type(wu).__name__, "len:", len(wu))
if isinstance(wu, dict):
    keys = list(wu.keys())
    print("first 10 keys:", keys[:10])
    aud = [k for k in keys if k.startswith("AUD")]
    bld = [k for k in keys if k.startswith("BLD")]
    print("AUD keys:", aud)
    print("BLD keys:", bld)
elif isinstance(wu, list):
    ids = [e.get("id") for e in wu]
    print("AUD ids:", [i for i in ids if isinstance(i,str) and i.startswith("AUD")])
    print("BLD ids:", [i for i in ids if isinstance(i,str) and i.startswith("BLD")])
print("units key sample:", json.dumps(cat.get("units"), ensure_ascii=False)[:400] if "units" in cat else "none")
