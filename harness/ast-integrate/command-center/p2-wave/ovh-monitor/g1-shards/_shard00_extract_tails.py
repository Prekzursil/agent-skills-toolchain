#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

WAVE = Path(__file__).resolve().parents[2]
IDS = [
    ln.strip()
    for ln in (WAVE / "ovh-monitor" / "g1-shards" / "shard-00.txt")
    .read_text(encoding="utf-8")
    .splitlines()
    if ln.strip()
]
want = set(IDS)
found: dict[str, dict] = {}
jsonl = WAVE / "ovh-monitor" / "g1-local-full.jsonl"
with jsonl.open(encoding="utf-8") as f:
    for ln in f:
        rec = json.loads(ln)
        if rec.get("id") in want:
            found[rec["id"]] = rec
print("hits", len(found), "of", len(IDS))
out = []
for uid in IDS:
    rec = found.get(uid) or {}
    tail = rec.get("tail") or rec.get("line") or ""
    fails = [x for x in str(tail).splitlines() if "FAILED" in x]
    last = fails[-1] if fails else str(tail)[-400:]
    print(f"{uid}\t{rec.get('cls')}\t{last[:220]}")
    out.append(
        {
            "id": uid,
            "ok": rec.get("ok"),
            "cls": rec.get("cls"),
            "line": rec.get("line"),
            "last": last[:400],
            "tail": str(tail)[-1500:],
        }
    )
(WAVE / "ovh-monitor" / "g1-shards" / "_shard00_census_tails.json").write_text(
    json.dumps(out, indent=2) + "\n", encoding="utf-8"
)
