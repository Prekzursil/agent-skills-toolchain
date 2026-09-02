#!/usr/bin/env python3
"""Pull last known measure tails for current shard-03 IDs from jsonl dumps."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
IDS = [ln.strip() for ln in (HERE / "shard-03.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
WANT = set(IDS)

hits: dict[str, dict] = {}
for p in sorted(HERE.glob("*.jsonl")):
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        continue
    for ln in text.splitlines():
        if not ln.strip().startswith("{"):
            continue
        try:
            rec = json.loads(ln)
        except json.JSONDecodeError:
            continue
        uid = rec.get("id")
        if uid not in WANT:
            continue
        hits.setdefault(uid, {})[p.name] = {
            "ok": rec.get("ok") or rec.get("status"),
            "line": rec.get("line") or rec.get("last") or "",
            "cls": rec.get("cls"),
            "tail": (rec.get("tail") or "")[-900:],
        }

out = []
for uid in IDS:
    recs = hits.get(uid) or {}
    last = None
    for src, rec in recs.items():
        last = rec
        last["src"] = src
    tail = (last or {}).get("tail") or ""
    fail = ""
    for ln in tail.splitlines():
        s = ln.strip()
        if s.startswith("FAILED:") or "Error:" in s or "Error " in s[:40]:
            fail = s[:240]
    out.append(
        {
            "id": uid,
            "n_src": len(recs),
            "line": (last or {}).get("line"),
            "fail": fail,
            "tail_end": tail[-400:],
        }
    )

dest = HERE / "_s03_prior.json"
dest.write_text(json.dumps({"n": len(out), "rows": out}, indent=2) + "\n", encoding="utf-8")
print("wrote", dest)
for r in out:
    print(f"{r['id']:10} src={r['n_src']} {(r['fail'] or r['line'] or '')[:140]}")
