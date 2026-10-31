import json, os, sys
uid = sys.argv[1]
root = os.path.join(os.path.expanduser("~"), "p2-g1")
p = os.path.join(root, "command-center", "receipts", uid + ".json")
d = json.load(open(p, encoding="utf-8"))
out = os.path.join(root, "_shard12-w2", uid + "-receipt-dump.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(d, f, indent=1, ensure_ascii=False)
print("wrote", out)
