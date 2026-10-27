import json
cat = json.load(open(r"C:\Users\Prekzursil\p2-g1\command-center\WORK-UNIT-CATALOG.json", encoding="utf-8"))
ids = ["IMP-0165","IMP-0194","IMP-0195","IMP-0198","IMP-0202","IMP-0204","IMP-0218","IMP-0219","IMP-0221","IMP-0222","IMP-0224","IMP-0228"]
out = {}
for u in cat["work_units"]:
    if isinstance(u, dict) and u.get("id") in ids:
        out[u["id"]] = u
json.dump(out, open(r"C:\Users\Prekzursil\p2-g1\_shard12-w2\entries.json","w",encoding="utf-8"), indent=1)
missing = [i for i in ids if i not in out]
print("MISSING:", missing)
for i in ids:
    e = out.get(i)
    if not e:
        continue
    print("===", i)
    for k in ("output_path","probes","named_probes","dependencies","owner_gate","gate","completion_sentinel","output_schema"):
        if k in e:
            v = json.dumps(e[k], ensure_ascii=False)
            print(f"  {k}: {v[:400]}")
