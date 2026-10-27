import json, sys
cat = json.load(open(r"C:\Users\Prekzursil\p2-g1\command-center\WORK-UNIT-CATALOG.json", encoding="utf-8"))
ids = ["IMP-0165","IMP-0194","IMP-0195","IMP-0198","IMP-0202","IMP-0204","IMP-0218","IMP-0219","IMP-0221","IMP-0222","IMP-0224","IMP-0228"]
units = cat.get("units", cat) if isinstance(cat, dict) else cat
out = {}
if isinstance(units, dict):
    for i in ids:
        out[i] = units.get(i)
elif isinstance(units, list):
    for u in units:
        i = u.get("id")
        if i in ids:
            out[i] = u
json.dump(out, open(r"C:\Users\Prekzursil\p2-g1\_shard12-w2\entries.json","w",encoding="utf-8"), indent=1)
missing = [i for i in ids if i not in out]
print("MISSING:", missing)
for i in ids:
    e = out.get(i)
    if e:
        print("===", i, "===")
        print("output_path:", e.get("output_path"))
        print("probes:", e.get("probes"))
        print("dependencies:", e.get("dependencies"))
        print("desc:", (e.get("description") or "")[:300])
