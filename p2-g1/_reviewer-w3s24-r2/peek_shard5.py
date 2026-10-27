import json
from pathlib import Path

p = Path(r"C:/Users/Prekzursil/p2-g1/_p2shard5-w3-review/VERDICTS.json")
d = json.loads(p.read_text(encoding="utf-8"))
vs = d.get("verdicts", {})
for uid, v in vs.items():
    if not isinstance(v, dict):
        continue
    se = v.get("schema_errors")
    rce = v.get("receipt_core_errors")
    print(uid, "| verdict:", v.get("verdict"),
          "| n_schema_err:", se if isinstance(se, int) else (len(se) if isinstance(se, list) else None),
          "| n_core_err:", rce if isinstance(rce, int) else (len(rce) if isinstance(rce, list) else None))
    if isinstance(se, list) and se:
        print("   first schema err:", str(se[0])[:200])
    if isinstance(rce, list) and rce:
        print("   first core err:", str(rce[0])[:200])

print()
print("=== shard23 battery out (schema check shape) ===")
b = json.loads(Path(r"C:/Users/Prekzursil/p2-g1/_p2shard23-w3-review/_w3s23_battery_out.json").read_text(encoding="utf-8"))
sample = list(b.items())[0] if isinstance(b, dict) else None
if sample:
    uid, row = sample
    print(uid, "| keys:", sorted(row.keys()) if isinstance(row, dict) else type(row))
    if isinstance(row, dict):
        for k in row:
            if "schema" in k.lower():
                print("  ", k, "=", str(row[k])[:300])
