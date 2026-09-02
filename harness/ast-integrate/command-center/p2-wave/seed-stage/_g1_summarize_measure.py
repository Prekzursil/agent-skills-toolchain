#!/usr/bin/env python3
import json
from collections import Counter
from pathlib import Path

rows = [json.loads(l) for l in Path("/tmp/g1-class-mod.measure.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
ok = [r for r in rows if r.get("ok")]
fail = [r for r in rows if not r.get("ok")]
print(f"n={len(rows)} ok={len(ok)} fail={len(fail)}")
print("OK_IDS", " ".join(r["id"] for r in ok))
c = Counter()
for r in fail:
    line = r.get("line") or ""
    if "ModuleNotFoundError" in line or "No module named" in line:
        c["ModuleNotFoundError"] += 1
    elif "AttributeError" in line:
        c["AttributeError"] += 1
    else:
        c["probe-exit-other"] += 1
print("FAIL_CLS", dict(c))
