#!/usr/bin/env python3
import json
from pathlib import Path

p = Path("/home/prekzursil/p2-g1/_g1_shard05_remeasure2.jsonl")
ok = []
fail = []
for ln in p.read_text(encoding="utf-8").splitlines():
    rec = json.loads(ln)
    line = str(rec.get("line") or "")
    if rec.get("ok") and line.startswith("SUCCESS:delivered"):
        ok.append(rec["id"])
    else:
        fail.append((rec["id"], line))
print("n", len(ok) + len(fail), "ok", len(ok), "fail", len(fail))
print("OK", " ".join(ok))
print("---FAIL---")
for uid, line in fail:
    print(uid, line)
