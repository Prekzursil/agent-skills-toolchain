#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

OK = {
    "ADV-0018",
    "ADV-0047",
    "ADV-0076",
    "AUD-0033",
    "CC-0014",
    "IMP-0005",
    "IMP-0150",
    "IMP-0245",
    "IMP-0270",
    "IMP-0464",
    "RES-0004",
    "TST-0173",
    "WFA-0045",
}
emit_p = Path.home() / "p2-g1-shard17.jsonl"
emit: dict = {}
for line in emit_p.read_text(encoding="utf-8").splitlines():
    if line.strip():
        rec = json.loads(line)
        emit[rec["id"]] = rec
reasons: Counter[str] = Counter()
for uid, rec in sorted(emit.items()):
    if uid in OK:
        print(f"{uid}\tOK\tg1={rec.get('g1')}")
        continue
    last = rec.get("measure_last") or rec.get("g1") or ""
    emit_last = rec.get("emit_last2") or rec.get("emit_last") or ""
    blob = " ".join([last, emit_last, rec.get("measure_tail") or "", rec.get("emit_tail") or ""])
    if "ModuleNotFoundError" in blob:
        kind = "missing-module"
    elif "ImportError" in blob:
        kind = "import-error"
    elif "schema accepted garbage" in blob or "schema does not discriminate" in blob:
        kind = "schema-garbage"
    elif "_NS is not JSON serializable" in blob or "Object of type Result" in blob or "Object of type _NS" in blob:
        kind = "stub-_NS"
    elif "AttributeError" in blob:
        kind = "attr-error"
    elif "TypeError" in blob:
        kind = "type-error"
    elif "manifest-sha-mismatch" in last:
        kind = "manifest-sha-mismatch"
    elif "probe-exit" in last:
        kind = "probe-exit"
    else:
        kind = (last or "other")[:50]
    reasons[kind] += 1
    print(f"{uid}\t{kind}\tmeasure={last[:80]}\temit={emit_last[:90]}")
print("COUNTS", dict(reasons))
print("emit_ids", len(emit), "ok_in_emit", sum(1 for u in emit if u in OK))
