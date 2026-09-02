"""Build per-shard work specs for the 28.08 parallel repair batches.

Reads the latest full census jsonl + the prior run's live rerun jsonl, and emits
_claude28/shard-XX.spec.json with still-failing IDs, their reason class and tail.
Idempotent: safe to re-run between batches.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OVH = os.path.dirname(HERE)
FULL = os.path.join(OVH, "g1-local-full.jsonl")
RERUN = os.path.join(OVH, "g1-fails-rerun.jsonl")
OUT = os.path.join(HERE, "_claude28")
os.makedirs(OUT, exist_ok=True)

status = {}  # id -> row dict (last occurrence wins)
for path in (FULL, RERUN):
    if not os.path.exists(path):
        continue
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            uid = row.get("id") or row.get("unit") or row.get("uid")
            if uid:
                status[uid] = row

shards = sorted(
    n for n in os.listdir(HERE)
    if n.startswith("shard-") and n.endswith(".txt") and n.count(".") == 1
)
summary = {}
for name in shards:
    ids = [l.strip() for l in open(os.path.join(HERE, name), encoding="utf-8") if l.strip()]
    failing, ok_now, unknown = [], [], []
    for uid in ids:
        row = status.get(uid)
        if row is None:
            unknown.append(uid)
            continue
        ok = row.get("ok")
        if ok is None:
            res = str(row.get("result", "")) + str(row.get("line", ""))
            ok = "SUCCESS:delivered" in res
        if ok:
            ok_now.append(uid)
        else:
            failing.append({
                "id": uid,
                "cls": row.get("cls") or row.get("class") or "",
                "tail": (row.get("tail") or row.get("reason") or str(row))[-1500:],
            })
    spec = {
        "shard": name,
        "n_ids": len(ids),
        "ok_now": ok_now,
        "unknown": unknown,
        "failing": failing,
    }
    out_path = os.path.join(OUT, name.replace(".txt", ".spec.json"))
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=1)
    summary[name] = {"total": len(ids), "fail": len(failing), "ok_now": len(ok_now), "unknown": len(unknown)}

print(json.dumps(summary, indent=1))
