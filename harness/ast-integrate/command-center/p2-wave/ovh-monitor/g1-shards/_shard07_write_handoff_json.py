#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

G = Path(__file__).resolve().parent
IDS = [ln.strip() for ln in (G / "shard-07.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
ART = re.compile(r"artifact (\S+) bytes=(\d+) sha256=([0-9a-f]+)")
FAILED = re.compile(r"FAILED:[A-Z0-9-]+[^\n]{0,200}")
rows: dict[str, dict] = {}
for name in ("_shard07_g1_measure.jsonl", "_shard07_g1_remeasure.jsonl"):
    p = G / name
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            rows[rec["id"]] = rec
rem = (G / "shard-07.remaining.txt").read_bytes()
units = []
for uid in IDS:
    rec = rows.get(uid) or {}
    tail = rec.get("tail") or ""
    art = ART.search(tail)
    fails = FAILED.findall(tail)
    units.append(
        {
            "id": uid,
            "ok": bool(rec.get("ok")),
            "last": rec.get("last") or "NO-MEASURE",
            "rc": rec.get("rc"),
            "artifact": (
                {"path": art.group(1), "bytes": int(art.group(2)), "sha256": art.group(3)}
                if art
                else None
            ),
            "fail_msg": fails[-1] if fails else None,
        }
    )
out = {
    "shard": 7,
    "assigned_n": len(IDS),
    "measured_n": len(rows),
    "unmeasured": [u for u in IDS if u not in rows],
    "ok": sum(1 for u in units if u["ok"]),
    "fail": sum(1 for u in units if not u["ok"]),
    "ok_ids": [u["id"] for u in units if u["ok"]],
    "fail_ids": [u["id"] for u in units if not u["ok"]],
    "remaining_path": str(G / "shard-07.remaining.txt"),
    "remaining_bytes": len(rem),
    "remaining_fp": hashlib.sha256(rem).hexdigest(),
    "wave1_jsonl_bytes": (G / "_shard07_g1_measure.jsonl").stat().st_size,
    "wave2_jsonl_bytes": (G / "_shard07_g1_remeasure.jsonl").stat().st_size,
    "units": units,
}
dest = G / "shard-07.handoff.json"
dest.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
print("wrote", dest, "ok", out["ok"], "fail", out["fail"], "unmeasured", out["unmeasured"])
