#!/usr/bin/env python3
"""Try per-label attempt-selection variants; find which yields 18 wave-4 shards."""
import json, glob, os
from pathlib import Path

WF = Path(r"C:/Users/Prekzursil/.claude/projects/C--Users-Prekzursil/13dd0812-e887-4a76-9d0e-4c6e6d30a937/subagents/workflows/wf_a81de287-702")
S10 = ['IMP-0305','IMP-0306','IMP-0311','IMP-0323','IMP-0324','IMP-0329',
       'IMP-0330','IMP-0332','IMP-0333','IMP-0338','IMP-0350','IMP-0355']

def find_structured(jsonl_path):
    best = None
    with open(jsonl_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if "StructuredOutput" not in line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            msg = d.get("message") or {}
            c = msg.get("content")
            if not isinstance(c, list):
                continue
            for b in c:
                if isinstance(b, dict) and b.get("type") == "tool_use" and \
                        str(b.get("name","")).lower() == "structuredoutput":
                    best = b.get("input")
    return best

attempts = {}  # label -> list of (mtime, structured_or_None)
for m in WF.glob("*.meta.json"):
    try:
        label = json.load(open(m, encoding="utf-8")).get("description")
    except Exception:
        continue
    if not label or not label.startswith("build:"):
        continue
    j = m.with_name(m.stem.replace(".meta","") + ".jsonl")
    if not j.is_file():
        continue
    s = find_structured(j)
    attempts.setdefault(label, []).append((j.stat().st_mtime, s))
for label in attempts:
    attempts[label].sort()

def cum_for(pick):
    pending = list(S10); seen = set(pending); cum = {}
    for wave in (1,2,3,4):
        for si in range(24):
            label = f"build:w{wave}s{si}"
            picked = pick(attempts.get(label, []))
            if picked is None:
                continue
            s = picked[1] or {}
            for u in (s.get("units") or []):
                if u.get("state") == "built-awaiting-review" and u["id"] not in seen:
                    pending.append(u["id"]); seen.add(u["id"])
        cum[wave] = len(pending)
    n_shards = (len(pending) + 11)//12
    return cum, n_shards, pending

variants = {
    "newest-valid": lambda a: ([x for x in a if x[1] is not None] or [None])[-1],
    "oldest-valid": lambda a: ([x for x in a if x[1] is not None] or [None])[0],
    "newest-any (None if latest errored)": lambda a: a[-1] if a and a[-1][1] is not None else None,
}
for name, pick in variants.items():
    cum, n_shards, pending = cum_for(pick)
    print(f"{name}: cum={cum} shards={n_shards}")
    if 197 <= len(pending) <= 216:
        mine = pending[144:156]
        print("  MATCH 18-20 shards; shard12 =", mine)
        json.dump(pending, open(r"C:/Users/Prekzursil/p2-g1/_p2shard12-w4/_pending_variant.json","w"), indent=1)
