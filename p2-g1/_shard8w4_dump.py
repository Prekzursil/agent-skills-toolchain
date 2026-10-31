import json, sys
uid, section = sys.argv[1], sys.argv[2]
r = json.load(open("command-center/receipts/" + uid + ".json", encoding="utf-8"))
v = r.get(section)
if v is None:
    print("NO SECTION", section)
else:
    print(json.dumps(v, indent=1, ensure_ascii=False)[:4000])
if len(sys.argv) > 3 and sys.argv[3] == "evidence":
    for e in r.get("evidence", []):
        print("ANCHOR:", e.get("anchor"))
        for p in e.get("probes", []):
            print(" role:", p.get("role"), "| rc:", p.get("exit_code"))
            print(" raw:", (p.get("raw_output") or "")[:700])
            print(" ---")
