#!/usr/bin/env python3
"""Resume audit scratch: receipts census + journal dropped-agent mapping."""
import json
from collections import Counter
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
RCPT = REPO / "command-center" / "receipts"
JRN = Path(r"C:\Users\Prekzursil\.claude\projects\C--Users-Prekzursil"
           r"\13dd0812-e887-4a76-9d0e-4c6e6d30a937\subagents\workflows"
           r"\wf_a81de287-702\journal.jsonl")

# --- receipts census -------------------------------------------------------
states = Counter()
closed_by_reviewer = 0
open_reviewer_absent = 0
for p in RCPT.glob("*.json"):
    try:
        r = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        states["UNPARSEABLE"] += 1
        continue
    st = str(r.get("state") or "?").upper()
    states[st] += 1
    rv = r.get("reviewer") if isinstance(r.get("reviewer"), dict) else {}
    if st == "SUCCESS" and str(rv.get("verdict") or "").upper() == "PASS" and rv.get("independent") is True:
        closed_by_reviewer += 1
    fb = r.get("failure") if isinstance(r.get("failure"), dict) else None
    if fb and "reviewer-absent" in [str(c) for c in (fb.get("classification") or [])]:
        open_reviewer_absent += 1
print("RECEIPTS-BY-STATE:", dict(states))
print("CLOSED-BY-INDEPENDENT-REVIEWER:", closed_by_reviewer)
print("STILL-REVIEWER-ABSENT-OPEN:", open_reviewer_absent)

# --- journal: map dropped (failed) agent keys to their started labels ------
lines = JRN.read_text(encoding="utf-8", errors="replace").splitlines()
starts, fails, results = {}, {}, []
for ln in lines:
    try:
        o = json.loads(ln)
    except Exception:
        continue
    k = o.get("key")
    if o.get("type") == "started":
        starts[k] = o.get("label")
    elif o.get("type") == "failed":
        fails[k] = starts.get(k, "?")
    elif o.get("type") == "result":
        results.append(o.get("label") or (o.get("result") or {}).get("summary", "")[:40])
print("DROPPED-AGENTS:", json.dumps(fails, indent=1))
print("RESULT-LABELS (first 20):", json.dumps(results[:20], indent=1))
