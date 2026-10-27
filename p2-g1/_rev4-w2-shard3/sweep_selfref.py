#!/usr/bin/env python3
"""Structural-deadlock sweep: across ALL receipts, how many self-referential
receipt-output units have gate condition 3 SATISFIED vs UNSATISFIED, and does
any receipt anywhere contain a self-row sha that matches its own file?"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / "p2-g1" / "platform" / "lib"))
import receipt_schema_gate as rsg

REPO = Path.home() / "p2-g1"
rows = []
selfref = {"sat": 0, "unsat": 0, "err": 0}
selfref_sha_match = 0
total = 0
for p in sorted((REPO / "command-center" / "receipts").glob("*.json")):
    total += 1
    try:
        r = json.loads(p.read_bytes().decode("utf-8-sig"))
    except Exception:
        continue
    if not isinstance(r, dict):
        continue
    own_rel = "command-center/receipts/" + p.name
    arts = [a for a in r.get("artifacts", []) if isinstance(a, dict)]
    self_rows = [a for a in arts
                 if str(a.get("path", "")).replace("\\", "/") == own_rel]
    if not self_rows:
        continue
    raw = p.read_bytes()
    live = hashlib.sha256(raw).hexdigest()
    live_norm = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
    sr = self_rows[0]
    sha_hit = sr.get("sha256") in (live, live_norm)
    if sha_hit:
        selfref_sha_match += 1
    try:
        g = rsg.evaluate_gate_a(r, repo_root=REPO)
        c3 = [c for c in g.blocking_conditions + [c for c in g.conditions if c.outcome == "SATISFIED"] if c.n == 3]
        outcome = c3[0].outcome if c3 else "missing"
    except Exception:
        outcome = "err"
    if outcome == "SATISFIED":
        selfref["sat"] += 1
    elif outcome in ("UNSATISFIED", "NOT_CHECKED"):
        selfref["unsat"] += 1
    else:
        selfref["err"] += 1
    rows.append((p.stem, r.get("state"), outcome, sha_hit))

print("total receipts:", total)
print("self-referential receipts found:", len(rows))
print("cond3 outcomes among self-referential:", selfref)
print("self-rows whose sha256 equals the live file hash:", selfref_sha_match)
sat = [x for x in rows if x[2] == "SATISFIED"]
print("SATISFIED examples:", sat[:5])
