#!/usr/bin/env python3
"""Aggregate module_gaps / edited / unresolved across g1-shards/_claude28/shard-*.result.json."""
import collections
import glob
import json
import os

D = "/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/_claude28"
gaps = collections.defaultdict(set)
edited = set()
unres = []
for f in sorted(glob.glob(os.path.join(D, "shard-*.result.json"))):
    d = json.load(open(f, encoding="utf-8", errors="replace"))
    for e in d.get("edited", []):
        edited.add(e["id"] if isinstance(e, dict) else e)
    mg = d.get("module_gaps", {})
    if isinstance(mg, dict):
        for k, v in mg.items():
            for i in (v if isinstance(v, list) else [v]):
                gaps[k].add(i if isinstance(i, str) else json.dumps(i)[:40])
    elif isinstance(mg, list):
        for e in mg:
            if isinstance(e, dict):
                k = e.get("module") or e.get("file") or e.get("gap") or str(e)[:60]
                for i in (e.get("ids") or [e.get("id")]):
                    if i:
                        gaps[k].add(i)
    for u in d.get("unresolved", []):
        unres.append(u if isinstance(u, str) else u.get("id"))
allids = set().union(*gaps.values()) if gaps else set()
print("edited", len(edited))
print("gap-keys", len(gaps), "gap-ids", len(allids))
for k, v in sorted(gaps.items(), key=lambda kv: -len(kv[1])):
    print(f"{len(v):3d} {k}: {' '.join(sorted(v))}")
print("unresolved", len(unres), unres)
