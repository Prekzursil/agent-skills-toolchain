#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
IDS = [
    ln.strip()
    for ln in (HERE / "shard-04.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
want = set(IDS)
found = {}
for name in ("class-other.measure.jsonl", "_envelope_measure.jsonl"):
    p = HERE / name
    if not p.is_file():
        continue
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rec = json.loads(line)
        except Exception:
            continue
        uid = rec.get("id")
        if uid in want:
            found.setdefault(uid, []).append(
                {
                    "src": name,
                    "ok": rec.get("ok"),
                    "cls": rec.get("cls"),
                    "line": rec.get("line") or rec.get("last"),
                    "tail": (rec.get("tail") or "")[-1200:],
                }
            )
print(f"found {len(found)}/{len(IDS)}")
for uid in IDS:
    recs = found.get(uid) or []
    if not recs:
        print(f"{uid:10} NO-PRIOR")
        continue
    rec = recs[-1]
    print(f"{uid:10} ok={rec.get('ok')} cls={rec.get('cls')} {str(rec.get('line'))[:80]}")
    tail = rec.get("tail") or ""
    if rec.get("ok") is not True and tail:
        for ln in tail.splitlines()[-6:]:
            print(f"    {ln[:180]}")

(HERE / "_shard04_prior.json").write_text(json.dumps(found, indent=2), encoding="utf-8")
