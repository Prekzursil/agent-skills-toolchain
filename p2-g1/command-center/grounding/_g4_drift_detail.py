"""Deterministic classification of the drifted files. Pure counting, no judgement."""

import collections
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
with path.open("r", encoding="utf-8") as f:
    d = json.load(f)

print("SUMMARY BLOCK:", json.dumps(d["summary"], indent=2))

skills = d["skills"]
sample_key = next(iter(skills))
print("\nsample skill entry key:", sample_key)
print(json.dumps(skills[sample_key], indent=2)[:900])

# Aggregate every per-file verdict across all skills.
status_counter = collections.Counter()
per_status_paths = collections.defaultdict(list)
for sname, entry in skills.items():
    files = entry.get("files") or entry.get("paths") or []
    if isinstance(files, dict):
        items = files.items()
    else:
        items = [(f.get("path"), f) for f in files]
    for rel, rec in items:
        st = rec.get("status") if isinstance(rec, dict) else rec
        status_counter[st] += 1
        if st != "IDENTICAL":
            per_status_paths[st].append(f"{sname}/{rel}")

print("\nALL FILE VERDICTS:")
for s, n in status_counter.most_common():
    print(f"  {s:18s} {n}")

print("\nNON-IDENTICAL, BY STATUS:")
for s in sorted(per_status_paths):
    paths = sorted(per_status_paths[s])
    print(f"\n### {s}  n={len(paths)}")
    for p in paths:
        print("   ", p)

nm = d["needs_merge"]
print(f"\nneeds_merge n={len(nm)}; first entry type={type(nm[0]).__name__}")
print(json.dumps(nm[0], indent=2) if isinstance(nm[0], dict) else nm[0])
