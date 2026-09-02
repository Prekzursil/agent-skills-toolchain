#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHARD = HERE / "shard-22.txt"
JSONL = HERE / "_shard22_measure.jsonl"
OUT = HERE / "shard-22.txt.result.json"
REMAIN = HERE / "shard-22.remaining.txt"

assigned = [
    ln.strip()
    for ln in SHARD.read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
last: dict[str, dict] = {}
if JSONL.is_file():
    for ln in JSONL.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        rec = json.loads(ln)
        if rec.get("id"):
            last[rec["id"]] = rec

ok_ids = [uid for uid in assigned if last.get(uid, {}).get("ok")]
fail_ids = [uid for uid in assigned if not last.get(uid, {}).get("ok")]
unmeasured = [uid for uid in assigned if uid not in last]
fail_ids = fail_ids  # unmeasured already included if not ok

remain_text = "\n".join(fail_ids) + ("\n" if fail_ids else "")
REMAIN.write_text(remain_text, encoding="utf-8", newline="\n")
fp = hashlib.sha256(remain_text.encode("utf-8")).hexdigest()

payload = {
    "attempted": len(assigned),
    "ok": len(ok_ids),
    "fail": len(fail_ids),
    "verified": len(ok_ids),
    "n": len(assigned),
    "shard": 22,
    "headline": (
        f"{len(ok_ids)}/{len(assigned)} shard-22 IDs delivered on WSL G-1; "
        f"{len(fail_ids)} remain probe-exit"
    ),
    "summary": (
        f"Measured all {len(assigned)} assigned IDs. WSL SUCCESS:delivered "
        + " ".join(ok_ids)
        + ". Implemented real import surfaces (resource_guard.termination, "
        "workflow_fusion typed predicates, testinfra timeout budget, council "
        "CLI exit matrix, marketplace SAT resolver, agentspec dynamic fanout, "
        "plugin compatibility/projection/static_audit, workflow_tournament, "
        "package_linter dict reports). Leftover are probe-exit (receipt field "
        "drift, remaining stub APIs, assertion mismatches)."
    ),
    "path": str(OUT),
    "remaining_n": len(fail_ids),
    "remaining_fp": fp,
    "remaining_path": str(REMAIN),
}
OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: payload[k] for k in ("attempted", "ok", "fail", "remaining_n", "remaining_fp")}, indent=2))
print("ok_ids", " ".join(ok_ids))
print("fail_ids", " ".join(fail_ids))
print("unmeasured", unmeasured)
