#!/usr/bin/env python3
"""Reconstruct the wave-4 pendingReview ordering from workflow subagent transcripts."""
import json, re
from pathlib import Path
from collections import defaultdict

WF = Path(r"C:/Users/Prekzursil/.claude/projects/C--Users-Prekzursil/13dd0812-e887-4a76-9d0e-4c6e6d30a937/subagents/workflows/wf_a81de287-702")

def label_of(meta_path):
    try:
        return json.load(open(meta_path, encoding="utf-8")).get("description")
    except Exception:
        return None

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
                        str(b.get("name", "")).lower() == "structuredoutput":
                    best = b.get("input")
    return best

rows = []
for m in WF.glob("*.meta.json"):
    label = label_of(m)
    if not label:
        continue
    j = m.with_name(m.stem.replace(".meta", "") + ".jsonl")
    if not j.is_file():
        continue
    rows.append((label, j.stat().st_mtime, j))

results = {}
for label, mt, j in sorted(rows, key=lambda r: r[1]):
    s = find_structured(j)
    if s is not None:
        results[label] = (mt, s)

out = {}
for label, (mt, s) in results.items():
    units = s.get("units") if isinstance(s, dict) else None
    if isinstance(units, list):
        out[label] = {"mtime": mt, "n_units": len(units),
                      "units": [[u.get("id"), u.get("state") or u.get("verdict")] for u in units if isinstance(u, dict)]}
json.dump(out, open(r"C:/Users/Prekzursil/p2-g1/_p2shard12-w4/_agent_results.json", "w", encoding="utf-8"), indent=1)

kinds = defaultdict(list)
for label in results:
    mm = re.match(r"^(build|review):w(\d+)s(\d+)$", label)
    if mm:
        kinds[(mm.group(1), mm.group(2))].append(int(mm.group(3)))
for k in sorted(kinds, key=lambda x: (x[0], int(x[1]))):
    print(k, "n=", len(kinds[k]), "shards:", sorted(kinds[k]))
for label in sorted(results):
    if label.startswith("partition"):
        s = results[label][1] or {}
        rids = s.get("ready_ids")
        print(label, "ready_ids n=", len(rids) if isinstance(rids, list) else "?", "| counts:", str(s.get("counts"))[:120])
