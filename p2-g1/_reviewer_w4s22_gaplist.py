#!/usr/bin/env python3
"""Identify the non-green remainder: unclosed SUCCESS, BLOCKED, NO-STATE, PARTIAL, BUILT."""
import json
import os
import re
from collections import Counter

base = "C:/Users/Prekzursil/p2-g1"
cat = json.load(open(os.path.join(base, "command-center", "WORK-UNIT-CATALOG.json"), encoding="utf-8"))
wu = cat["work_units"]
bs = chr(92)
unclosed = []
blocked = []
nostate = []
other = []
for u in wu:
    uid = u.get("id")
    op = (u.get("output_path") or "").replace(bs, "/")
    p = os.path.join(base, op) if op else None
    if not p or not os.path.isfile(p):
        nostate.append((uid, "receipt-missing"))
        continue
    try:
        r = json.load(open(p, encoding="utf-8"))
    except Exception:
        nostate.append((uid, "receipt-unparseable"))
        continue
    st = str(r.get("state") or "").upper()
    if st == "SUCCESS":
        rv = r.get("reviewer") if isinstance(r.get("reviewer"), dict) else {}
        if not (rv.get("verdict") == "PASS" and rv.get("independent") is True):
            unclosed.append((uid, json.dumps(rv)[:150]))
    elif st == "BLOCKED":
        fb = r.get("failure") or {}
        unclosed_block = {}
        blocked.append((uid, str(fb.get("classification"))[:120] or str(r.get("notes"))[:120]))
    elif st in ("PARTIAL", "BUILT"):
        other.append((uid, st))

print("== unclosed SUCCESS (%d)" % len(unclosed))
for uid, why in unclosed:
    print("  %s: %s" % (uid, why))
print("== BLOCKED (%d)" % len(blocked))
for uid, why in blocked:
    print("  %s: %s" % (uid, why))
print("== NO-STATE / missing (%d)" % len(nostate))
for uid, why in nostate:
    print("  %s: %s" % (uid, why))
print("== other (%d)" % len(other))
for uid, st in other:
    print("  %s: %s" % (uid, st))
