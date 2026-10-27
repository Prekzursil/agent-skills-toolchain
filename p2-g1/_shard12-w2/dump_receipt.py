import json, os, sys
uid = sys.argv[1]
p = os.path.join(os.path.expanduser("~"), "p2-g1", "command-center", "receipts", uid + ".json")
d = json.load(open(p, encoding="utf-8"))
print(json.dumps(d, indent=1, ensure_ascii=False))
