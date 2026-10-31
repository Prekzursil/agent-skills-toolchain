import json, os
ids = ["IMP-0165","IMP-0194","IMP-0195","IMP-0198","IMP-0202","IMP-0204","IMP-0218","IMP-0219","IMP-0221","IMP-0222","IMP-0224","IMP-0228"]
base = os.path.join(os.path.expanduser("~"), "p2-g1", "command-center", "receipts")
for i in ids:
    p = os.path.join(base, i + ".json")
    try:
        d = json.load(open(p, encoding="utf-8"))
    except Exception as e:
        print(i, "UNPARSEABLE", type(e).__name__, e)
        continue
    rev = d.get("reviewer") or {}
    fail = d.get("failure") or {}
    print(i,
      "state=" + str(d.get("state")),
      "sentinel=" + str(d.get("sentinel"))[:44],
      "rev=" + str(rev.get("verdict")) + "/" + str(rev.get("independent")) + "/" + str(rev.get("reviewer_id"))[:24],
      "fail=" + json.dumps(fail.get("classification")),
      "artifacts=" + str(len(d.get("artifacts") or [])),
      "evidence=" + str(len(d.get("evidence") or [])),
      "tests=" + str(len(d.get("tests") or [])))
