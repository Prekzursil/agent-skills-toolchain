import json
CAT = r"C:\Users\Prekzursil\p2-g1\command-center\WORK-UNIT-CATALOG.json"
IDS = ["AUD-0080","AUD-0082","AUD-0084","AUD-0095","AUD-0096","BLD-0001","BLD-0002","BLD-0004","BLD-0005","BLD-0010","BLD-0013","BLD-0014"]
with open(CAT, "r", encoding="utf-8") as f:
    cat = json.load(f)
wu = cat["work_units"]
out = {}
for e in wu:
    if isinstance(e, dict) and e.get("id") in IDS:
        out[e["id"]] = e
print("FOUND:", sorted(out))
print("MISSING:", [u for u in IDS if u not in out])
with open(r"C:\Users\Prekzursil\p2-g1\_w2shard5_resume\my_entries.json","w",encoding="utf-8") as f:
    json.dump(out, f, indent=1, ensure_ascii=False)
for uid in IDS:
    if uid not in out:
        continue
    e = out[uid]
    print("=== ", uid, " ===")
    for k in ("output_path","output_schema","owner_approval_required","phase","dependencies","timeout_seconds","completion_sentinel"):
        if k in e:
            print(" ", k, "=", json.dumps(e[k], ensure_ascii=False)[:400])
    print("  title:", json.dumps(e.get("title"), ensure_ascii=False)[:220])
    print("  q_or_t:", json.dumps(e.get("question_or_target"), ensure_ascii=False)[:600])
