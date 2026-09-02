#!/usr/bin/env python3
"""shard-01 scratch: inspect a $defs entry of the profiles schema."""
import json
import sys

path = sys.argv[1]
key = sys.argv[2] if len(sys.argv) > 2 else None
d = json.load(open(path, encoding="utf-8"))
defs = d.get("$defs") or d.get("definitions") or {}
print("n_defs:", len(defs))
if key:
    print(json.dumps(defs.get(key), indent=1)[:4000])
else:
    print(sorted(defs.keys()))
