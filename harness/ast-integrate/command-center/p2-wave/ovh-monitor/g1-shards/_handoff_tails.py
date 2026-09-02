import json
from collections import Counter
from pathlib import Path

SH = Path(__file__).resolve().parent
p2 = {}
for ln in (SH / "class-envelope.pass2.jsonl").read_text(encoding="utf-8").splitlines():
    rec = json.loads(ln)
    p2[rec["id"]] = rec
cls = Counter(r.get("cls") for r in p2.values() if not r.get("ok"))
print("pass2 fail classes", dict(cls))
for c in ("ModuleNotFoundError", "probe-file-missing"):
    print("==", c)
    for uid, rec in p2.items():
        if rec.get("cls") == c:
            print(uid, rec.get("line"))
            tail = rec.get("tail") or ""
            for line in tail.splitlines()[-6:]:
                print(" ", line[:200])
# confirm a few pass1 SUCCESS last lines
p1 = {}
for ln in (SH / "class-envelope.measure.jsonl").read_text(encoding="utf-8").splitlines():
    rec = json.loads(ln)
    p1[rec["id"]] = rec
print("== pass1 SUCCESS samples")
for uid in ("ARC-0007", "CNF-0001", "RES-0079", "SYN-0005", "ADV-0013"):
    rec = p1.get(uid) or {}
    print(uid, rec.get("ok"), rec.get("line"))
print("== pass2 SUCCESS last lines")
for uid in ("ADV-0003", "ADV-0030", "ADV-0064", "ADV-0068", "ADV-0112", "IMP-0261"):
    rec = p2.get(uid) or {}
    print(uid, rec.get("ok"), rec.get("line"))
