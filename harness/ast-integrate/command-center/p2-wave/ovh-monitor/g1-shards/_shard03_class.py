#!/usr/bin/env python3
import json
from pathlib import Path
d=json.loads(Path(__file__).with_name("_shard03_live.json").read_text(encoding="utf-8"))
print("n", d["n"], "ok", d["ok"], "fail", d["fail"])
for r in d["rows"]:
    if r.get("ok"):
        print("OK", r["id"])
        continue
    tail = r.get("tail") or ""
    hits=[ln.strip()[:180] for ln in tail.splitlines() if ln.strip().startswith("FAILED:") and "delivered" not in ln]
    print(r["id"], "|", hits[-1] if hits else r.get("line"))
