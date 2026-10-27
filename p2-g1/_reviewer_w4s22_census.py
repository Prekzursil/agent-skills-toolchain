#!/usr/bin/env python3
"""Census of all catalog units: receipt state + closure status (w4s22 reviewer)."""
import json
import os
import re
from collections import Counter

base = "C:/Users/Prekzursil/p2-g1"
cat = json.load(open(os.path.join(base, "command-center", "WORK-UNIT-CATALOG.json"), encoding="utf-8"))
wu = cat["work_units"]
total = len(wu)
states = Counter()
missing = 0
unparse = 0
closed_green = 0
success_no_pass = 0
unknown_tokens = 0
bs = chr(92)
for u in wu:
    uid = u.get("id")
    op = (u.get("output_path") or "").replace(bs, "/")
    p = os.path.join(base, op) if op else None
    if not p or not os.path.isfile(p):
        missing += 1
        states["MISSING"] += 1
        continue
    try:
        r = json.load(open(p, encoding="utf-8"))
    except Exception:
        unparse += 1
        states["UNPARSEABLE"] += 1
        continue
    st = str(r.get("state") or "").upper()
    states[st or "NO-STATE"] += 1
    if st == "SUCCESS":
        rv = r.get("reviewer") if isinstance(r.get("reviewer"), dict) else {}
        if rv.get("verdict") == "PASS" and rv.get("independent") is True:
            closed_green += 1
        else:
            success_no_pass += 1
    if uid and re.match(r"^(ARC|WFA|CC|IMP)-", str(uid)):
        unknown_tokens += 1

print("TOTAL catalog units:", total)
for k, v in states.most_common():
    print("  %-14s %d" % (k, v))
print("closed green (SUCCESS + reviewer PASS + independent):", closed_green)
print("SUCCESS but no valid PASS closure:", success_no_pass)
print("unknown-token ids (ARC/WFA/CC/IMP):", unknown_tokens)
print("progress: %d / %d = %.1f%%" % (closed_green, total, 100.0 * closed_green / total))
