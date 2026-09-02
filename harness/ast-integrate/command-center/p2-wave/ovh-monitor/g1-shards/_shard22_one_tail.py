#!/usr/bin/env python3
import json
import sys
from pathlib import Path

uid = sys.argv[1]
for ln in Path(__file__).with_name("_shard22_measure.jsonl").read_text(encoding="utf-8").splitlines():
    rec = json.loads(ln)
    if rec.get("id") == uid:
        print(rec.get("tail") or "")
        break
else:
    raise SystemExit(f"missing {uid}")
