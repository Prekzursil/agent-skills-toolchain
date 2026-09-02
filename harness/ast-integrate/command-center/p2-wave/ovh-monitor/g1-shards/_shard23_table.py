#!/usr/bin/env python3
from pathlib import Path
import json
import re

HERE = Path(__file__).resolve().parent
rows = json.loads((HERE / "_shard23_dump.json").read_text(encoding="utf-8"))
FAIL_RE = re.compile(r"(FAILED:|raise |sys\.exit|AssertionError|print\(.*fail)", re.I)
for r in rows:
    miss = [m for m in (r.get("miss") or []) if m != "__future__"]
    print(f"\n===== {r['id']} miss={miss[:8]} cmds={r['named_cmds']} sha={r['sha_match']} =====")
    tails = r.get("probe_tails") or {}
    for name, lines in tails.items():
        print(f"-- {name} --")
        for ln in lines[-16:]:
            print(ln)
