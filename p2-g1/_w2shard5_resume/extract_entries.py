import json, sys
CAT = r"C:\Users\Prekzursil\p2-g1\command-center\WORK-UNIT-CATALOG.json"
IDS = ["AUD-0080","AUD-0082","AUD-0084","AUD-0095","AUD-0096","BLD-0001","BLD-0002","BLD-0004","BLD-0005","BLD-0010","BLD-0013","BLD-0014"]
with open(CAT, "r", encoding="utf-8") as f:
    cat = json.load(f)
# catalog may be a dict keyed by id, or {"units": {...}} etc.
def entries(c):
    if isinstance(c, dict):
        for k in ("units","entries","work_units","catalog"):
            if k in c and isinstance(c[k], dict):
                return c[k]
        return c
    return {}
E = entries(cat)
out = {}
found = []
for uid in IDS:
    if uid in E:
        out[uid] = E[uid]
        found.append(uid)
print("TOP-LEVEL KEYS:", list(cat.keys())[:10] if isinstance(cat, dict) else type(cat))
print("TOTAL ENTRIES:", len(E))
print("FOUND:", found)
print("MISSING:", [u for u in IDS if u not in found])
with open(r"C:\Users\Prekzursil\p2-g1\_w2shard5_resume\my_entries.json","w",encoding="utf-8") as f:
    json.dump(out, f, indent=1, ensure_ascii=False)
# also print compact summary
for uid in found:
    e = E[uid]
    print("---", uid)
    for k in ("output_path","output_schema","owner_approval_required","phase","dependencies","id"):
        if k in e: print(" ", k, "=", json.dumps(e[k], ensure_ascii=False)[:300])
