#!/usr/bin/env python3
# Read-only program-wide progress scan: of 2007 catalog units, how many have a
# DELIVERED-candidate artifact (exists, parses, state=SUCCESS, reviewer PASS+independent)
# vs BLOCKED/FAILED/missing. No writes.
import json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
cat = json.load(open(REPO / "command-center/WORK-UNIT-CATALOG.json", encoding="utf-8"))
units = cat["work_units"]
tally = {"total": 0, "success_indep": 0, "success_noindep": 0, "blocked": 0,
         "failed": 0, "other_state": 0, "missing": 0, "empty": 0, "unparsable": 0}
missing_ids, blocked_ids, other_ids = [], [], []
for u in units:
    uid = u.get("id")
    op = u.get("output_path")
    tally["total"] += 1
    if not op:
        tally["missing"] += 1
        missing_ids.append(uid)
        continue
    p = REPO / op
    if not p.exists() or p.stat().st_size == 0:
        tally["missing"] if not p.exists() else None
        if not p.exists():
            tally["missing"] += 1
            missing_ids.append(uid)
        else:
            tally["empty"] += 1
            missing_ids.append(uid)
        continue
    try:
        doc = json.loads(p.read_bytes().decode("utf-8"))
    except Exception:
        tally["unparsable"] += 1
        continue
    st = doc.get("state")
    if st == "SUCCESS":
        rv = doc.get("reviewer") or {}
        if rv.get("verdict") == "PASS" and rv.get("independent") is True:
            tally["success_indep"] += 1
        else:
            tally["success_noindep"] += 1
    elif st == "BLOCKED":
        tally["blocked"] += 1
        blocked_ids.append(uid)
    elif st == "FAILED":
        tally["failed"] += 1
    else:
        tally["other_state"] += 1
        other_ids.append((uid, st))
print(json.dumps(tally, indent=1))
print("BLOCKED ids:", blocked_ids[:60])
print("OTHER-STATE ids:", other_ids[:60])
print("MISSING sample:", missing_ids[:30])
