#!/usr/bin/env python3
"""Emit repair ID lists (timeout / mod / probe-missing / sha / predicate) from g1-local-full.jsonl."""
import json
import re
from pathlib import Path

MON = Path(__file__).resolve().parent.parent / "ovh-monitor"
OUT = MON / "repair-claude"
OUT.mkdir(parents=True, exist_ok=True)

rows = {}
for line in (MON / "g1-local-full.jsonl").read_text(encoding="utf-8").splitlines():
    if line.strip():
        rec = json.loads(line)
        rows[rec["id"]] = rec

fails = [r for r in rows.values() if not r.get("ok")]
buckets = {"timeout": [], "mod": [], "probe-missing": [], "sha": [], "predicate": [], "assert": []}
mods = {}
for r in fails:
    tail = str(r.get("tail") or "")
    cls = r.get("cls") or ""
    if cls == "ModuleNotFoundError" or "ModuleNotFoundError" in tail:
        buckets["mod"].append(r["id"])
        m = re.search(r"ModuleNotFoundError: No module named '([^']+)'", tail)
        mods[r["id"]] = m.group(1) if m else "?"
    elif cls == "probe-file-missing":
        buckets["probe-missing"].append(r["id"])
    elif cls == "manifest-sha-mismatch" or "manifest-sha-mismatch" in tail:
        buckets["sha"].append(r["id"])
    elif cls.startswith("predicate") or "predicate:" in str(r.get("line") or ""):
        buckets["predicate"].append(r["id"])
    elif "TIMEOUT" in tail:
        buckets["timeout"].append(r["id"])
    else:
        buckets["assert"].append(r["id"])

for name, ids in buckets.items():
    (OUT / f"ids-{name}.txt").write_text("\n".join(sorted(ids)) + "\n", encoding="utf-8")
(OUT / "mods-by-id.json").write_text(json.dumps(mods, indent=1) + "\n", encoding="utf-8")
print(json.dumps({k: len(v) for k, v in buckets.items()}))
print(json.dumps(mods, indent=0))
