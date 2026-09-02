#!/usr/bin/env python3
import json
from pathlib import Path

p = Path(__file__).with_name("_shard14_measure.jsonl")
rows = []
for line in p.read_text(encoding="utf-8").splitlines():
    rec = json.loads(line)
    if rec.get("ok"):
        continue
    tail = rec.get("tail") or ""
    lines = tail.splitlines()
    keys = []
    for ln in lines:
        s = ln.strip()
        if (
            s.startswith("FAILED:")
            or "Error" in s
            or "ModuleNotFound" in s
            or "AssertionError" in s
            or "ImportError" in s
            or "TypeError" in s
            or "AttributeError" in s
            or "KeyError" in s
            or "ValueError" in s
            or "IndexError" in s
        ):
            keys.append(s[:240])
    rows.append(
        {
            "id": rec["id"],
            "last": rec["last"],
            "keys": keys[-8:],
            "tail_last": lines[-18:],
        }
    )
out = Path(__file__).with_name("_shard14_fail_compact.json")
out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
print(f"n_fail={len(rows)} wrote {out}")
for r in rows:
    print(f"\n## {r['id']}")
    for k in r["keys"][-4:]:
        print(" ", k)
