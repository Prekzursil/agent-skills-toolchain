from pathlib import Path
import json
p = Path(__file__).resolve().parent / "class-other.measure.jsonl"
n = 0
last = {}
ids = []
with p.open(encoding="utf-8") as fh:
    for ln in fh:
        if not ln.strip():
            continue
        n += 1
        rec = json.loads(ln)
        last[rec["id"]] = rec
        ids.append(rec["id"])
print("lines", n, "unique", len(last), "bytes", p.stat().st_size)
print("first3", ids[:3], "last3", ids[-3:])
print("ADV-0013", last.get("ADV-0013", {}).get("ok"), last.get("ADV-0013", {}).get("cls"), last.get("ADV-0013", {}).get("line"))
print("RES-0079", last.get("RES-0079", {}).get("ok"), last.get("RES-0079", {}).get("cls"))
print("CNF-0001", last.get("CNF-0001", {}).get("ok"), last.get("CNF-0001", {}).get("cls"), last.get("CNF-0001", {}).get("line"))
ok = sum(1 for r in last.values() if r.get("ok"))
print("unique_ok", ok, "unique_fail", len(last) - ok)
