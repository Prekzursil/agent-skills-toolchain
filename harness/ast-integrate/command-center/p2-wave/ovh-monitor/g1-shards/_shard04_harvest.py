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
hits = {}

for name in (
    "class-mod-harvest.json",
    "class-other.measure.json",
    "class-other.fail-summary.json",
    "_envelope_diag.json",
    "_envelope_measure.jsonl",
    "class-other.measure.jsonl",
):
    p = HERE / name
    if not p.is_file():
        continue
    text = p.read_text(encoding="utf-8", errors="replace")
    if p.suffix == ".jsonl":
        for i, line in enumerate(text.splitlines()):
            for uid in IDS:
                if uid in line:
                    hits.setdefault(uid, []).append({"src": name, "i": i, "line": line[:500]})
        continue
    try:
        data = json.loads(text)
    except Exception as exc:
        print(f"skip {name}: {exc}")
        continue
    if isinstance(data, dict):
        for uid in IDS:
            if uid in data:
                val = data[uid]
                if isinstance(val, dict):
                    hits.setdefault(uid, []).append(
                        {
                            "src": name,
                            "keys": list(val.keys())[:20],
                            "line": str(val.get("line") or val.get("fail_line") or "")[:300],
                            "tail": str(val.get("tail_head") or val.get("tail") or "")[:800],
                        }
                    )
                else:
                    hits.setdefault(uid, []).append({"src": name, "val": str(val)[:400]})
        failed = data.get("failed_msgs") if isinstance(data.get("failed_msgs"), dict) else {}
        for msg, n in failed.items():
            for uid in IDS:
                if uid in msg:
                    hits.setdefault(uid, []).append({"src": name, "failed_msg": msg, "n": n})
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                uid = item.get("id") or item.get("uid")
                if uid in want:
                    hits.setdefault(uid, []).append(
                        {
                            "src": name,
                            "line": str(item.get("line") or item.get("jsonl_line") or item.get("fail_line") or "")[:300],
                            "tail": str(item.get("tail_head") or item.get("tail") or "")[:800],
                        }
                    )

out = HERE / "_shard04_harvest.json"
out.write_text(json.dumps({"n": len(hits), "hits": hits}, indent=2), encoding="utf-8")
print(f"wrote {out} n={len(hits)}")
for uid in IDS:
    recs = hits.get(uid) or []
    line = ""
    for rec in recs:
        line = rec.get("line") or rec.get("failed_msg") or rec.get("tail") or ""
        if line:
            break
    print(f"{uid:10} n={len(recs)} {str(line)[:140]}")
