#!/usr/bin/env python3
import json
import re
from pathlib import Path

p = Path("/home/prekzursil/p2-g1/_g1_shard05_remeasure2.jsonl")
for ln in p.read_text(encoding="utf-8").splitlines():
    rec = json.loads(ln)
    if rec.get("ok"):
        continue
    tail = rec.get("tail") or ""
    hits = [
        t.strip()
        for t in tail.splitlines()
        if re.search(
            r"FAILED:[A-Z]|Error:|Unresolvable|KeyError|AttributeError|ImportError|TypeError|ModuleNotFound|NameError|FileNotFound|probe-exit:124",
            t,
        )
    ]
    reason = hits[0] if hits else rec.get("line")
    print(f"{rec['id']}\t{reason[:240]}")
