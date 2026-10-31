import json
from pathlib import Path

for name in ["_p2shard20-w3-review", "_p2shard15-w3-review", "_p2shard5-w3-review", "_p2shard14-w3-review", "_p2shard6-w3-review"]:
    p = Path(rf"C:/Users/Prekzursil/p2-g1/{name}/VERDICTS.json")
    if not p.exists():
        for alt in p.parent.glob("VERDICTS*.json"):
            p = alt
            break
    if not p.exists():
        print(name, "| no verdicts file")
        continue
    d = json.loads(p.read_text(encoding="utf-8"))
    vs = d.get("verdicts", {})
    dictvals = [v for v in vs.values() if isinstance(v, dict)]
    npass = sum(1 for v in dictvals if v.get("verdict") == "PASS")
    nfail = sum(1 for v in dictvals if v.get("verdict") == "FAIL")
    other = len(dictvals) - npass - nfail
    print(f"{name} | file={p.name} | pass={npass} fail={nfail} other={other} total={len(dictvals)}")
    # print field names of a PASS row and a FAIL row
    for want in ("PASS", "FAIL"):
        for uid, v in vs.items():
            if isinstance(v, dict) and v.get("verdict") == want:
                print(f"  {want} example {uid}: fields={sorted(v.keys())[:18]}")
                if want == "FAIL":
                    print("    fail_reason:", str(v.get("fail_reason"))[:250])
                break
