#!/usr/bin/env python3
"""Check whether TST receipts carry a self-referential artifacts row."""
import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
REPO = Path(r"C:/Users/Prekzursil/p2-g1")
UNITS = ["TST-0018", "TST-0028", "TST-0032", "TST-0057", "TST-0060",
         "TST-0066", "TST-0067", "TST-0068", "TST-0070"]
for uid in UNITS:
    fp = REPO / "command-center/receipts" / f"{uid}.json"
    r = json.loads(fp.read_text(encoding="utf-8"))
    out_rel = "command-center/receipts/{}.json".format(uid)
    rows = r.get("artifacts") or []
    norm = lambda s: str(s or "").replace(chr(92), "/")
    self_rows = [a for a in rows if norm(a.get("path")) == out_rel]
    print("== {}: rows={} self_rows={}".format(uid, len(rows), len(self_rows)))
    for a in rows[:5]:
        print("   ", norm(a.get("path"))[-60:], a.get("role"), a.get("bytes"))
