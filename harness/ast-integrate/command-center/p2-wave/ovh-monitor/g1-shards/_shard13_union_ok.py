#!/usr/bin/env python3
"""Union SUCCESS:delivered IDs from all shard-13 measure artifacts (jsonl + logs)."""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
IDS = [
    ln.strip()
    for ln in (HERE / "shard-13.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
OK_RE = re.compile(r"SUCCESS:delivered ([A-Z]{2,5}-\d{4})")
FAIL_RE = re.compile(r"FAILED:delivered ([A-Z]{2,5}-\d{4}) (.+)")

ok: dict[str, str] = {}
fail_last: dict[str, str] = {}
sources: dict[str, list[str]] = {u: [] for u in IDS}

files = [
    HERE / "_shard13_measure.jsonl",
    HERE / "_shard13_remeasure.jsonl",
    HERE / "_shard13_measure.log",
    HERE / "_shard13_remeasure.log",
]
# session logs that recorded later reconfirms
sess = Path(r"C:\Users\Prekzursil\.grok\sessions")
if sess.is_dir():
    for p in sess.rglob("*.log"):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "SUCCESS:delivered" in text and ("IMP-0126" in text or "shard13" in text.lower() or "IMP-0030" in text):
            files.append(p)

for path in files:
    if not path.is_file():
        continue
    text = path.read_text(encoding="utf-8", errors="replace")
    tag = str(path)
    if path.suffix == ".jsonl":
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            uid = rec.get("id")
            if uid not in sources:
                continue
            sources[uid].append(path.name)
            last = str(rec.get("last") or "")
            if rec.get("ok") or last == f"SUCCESS:delivered {uid}":
                ok[uid] = last
            elif last.startswith("FAILED:delivered"):
                fail_last[uid] = last
    else:
        for m in OK_RE.finditer(text):
            uid = m.group(1)
            if uid in sources:
                ok[uid] = f"SUCCESS:delivered {uid}"
                sources[uid].append(path.name)
        for m in FAIL_RE.finditer(text):
            uid, rest = m.group(1), m.group(2)
            if uid in sources and uid not in ok:
                fail_last[uid] = f"FAILED:delivered {uid} {rest[:80]}"

print("assigned", len(IDS))
print("ok", len(ok), sorted(ok))
missing_measure = [u for u in IDS if not sources[u] and u not in ok]
print("no-source", missing_measure)
print("fail_n", len(IDS) - len(ok))
for u in IDS:
    if u not in ok:
        print("FAIL", u, fail_last.get(u, "NO-LAST"))
