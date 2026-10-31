"""Summarise the deterministic differ output. No judgement, pure counting."""

import collections
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
with path.open("r", encoding="utf-8") as f:
    d = json.load(f)

print("TOP-LEVEL KEYS:", sorted(d.keys()))
for k, v in d.items():
    if isinstance(v, (int, str, bool)) or v is None:
        print(f"  {k} = {v!r}")
    elif isinstance(v, list):
        print(f"  {k}: list len={len(v)}")
    elif isinstance(v, dict):
        print(f"  {k}: dict len={len(v)}")

# find the per-file verdict list
cand = None
for k, v in d.items():
    if isinstance(v, list) and v and isinstance(v[0], dict) and "status" in v[0]:
        cand = k
        break
if cand is None:
    for k, v in d.items():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            print(f"  sample of {k}[0]:", json.dumps(v[0])[:400])
    sys.exit(0)

rows = d[cand]
print(f"\nPER-FILE LIST = {cand!r}, n={len(rows)}")
print("  row keys:", sorted(rows[0].keys()))
by_status = collections.Counter(r["status"] for r in rows)
for s, n in by_status.most_common():
    print(f"  {s:18s} {n}")

# skills touched, per status
per_skill = collections.defaultdict(collections.Counter)
for r in rows:
    skill = r.get("skill") or r.get("path", "?").split("/")[0]
    per_skill[skill][r["status"]] += 1

print(f"\nSKILLS WITH ANY NON-IDENTICAL ROW: {len(per_skill)}")
for skill in sorted(per_skill):
    c = per_skill[skill]
    print(f"  {skill:42s} " + " ".join(f"{k}={v}" for k, v in sorted(c.items())))
