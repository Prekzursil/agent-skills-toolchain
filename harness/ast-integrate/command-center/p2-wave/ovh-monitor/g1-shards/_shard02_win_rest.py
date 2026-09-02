#!/usr/bin/env python3
"""Resume shard-02 Windows probes for IDs not yet in the jsonl."""
from __future__ import annotations

import json
from pathlib import Path

import _shard02_win_probes as P

HERE = Path(__file__).resolve().parent
IDS = [
    ln.strip()
    for ln in (HERE / "shard-02.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
done: set[str] = set()
jsonl = HERE / "_shard02_win_probes.jsonl"
if jsonl.is_file():
    for ln in jsonl.read_text(encoding="utf-8").splitlines():
        if ln.strip():
            done.add(json.loads(ln)["id"])
rest = [uid for uid in IDS if uid not in done]
print(f"resume n={len(rest)} {rest}", flush=True)
ok = fail = 0
for uid in rest:
    cmds = P.cmds_for(uid)
    rec: dict = {"id": uid, "cmds": cmds, "probes": []}
    if not cmds:
        rec["error"] = "named-probes-absent"
        print(f"{uid} NO-PROBES", flush=True)
        fail += 1
        jsonl.open("a", encoding="utf-8", newline="\n").write(json.dumps(rec) + "\n")
        continue
    for cmd in cmds:
        r = P.run_one(cmd)
        rec["probes"].append(r)
        mark = "OK" if r["rc"] == 0 else f"FAIL:{r['rc']}"
        last = r["tail"].splitlines()[-1] if r["tail"] else ""
        print(f"{uid} {mark} {Path(r['cmd']).name} {last[:160]}", flush=True)
    if rec["probes"] and all(p["rc"] == 0 for p in rec["probes"]):
        ok += 1
    else:
        fail += 1
    jsonl.open("a", encoding="utf-8", newline="\n").write(json.dumps(rec) + "\n")
print(f"DONE rest ok={ok} fail={fail} attempted={len(rest)}", flush=True)
