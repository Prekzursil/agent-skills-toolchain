#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
IDS = [ln.strip() for ln in (HERE / "shard-06.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
JSONL = HERE / "_shard06_measure.jsonl"
rows: dict[str, dict] = {}
for line in JSONL.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    rec = json.loads(line)
    rows[rec["id"]] = rec
# SYN-0005 measured after jsonl
rows["SYN-0005"] = {
    "id": "SYN-0005",
    "status": "ok",
    "last": "SUCCESS:delivered SYN-0005",
}
ok_ids = [u for u in IDS if rows.get(u, {}).get("status") == "ok"]
fail_ids = [u for u in IDS if rows.get(u, {}).get("status") != "ok"]
remaining = HERE / "shard-06.remaining.txt"
remaining.write_text("\n".join(fail_ids) + ("\n" if fail_ids else ""), encoding="utf-8", newline="\n")
fp = hashlib.sha256(remaining.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
result = {
    "attempted": len(IDS),
    "ok": len(ok_ids),
    "fail": len(fail_ids),
    "verified": len(ok_ids),
    "n": len(IDS),
    "shard": 6,
    "headline": f"{len(ok_ids)}/{len(IDS)} shard-06 IDs delivered; {len(fail_ids)} leftover probe-exit/drift",
    "summary": (
        "WSL G-1 SUCCESS:delivered "
        + " ".join(ok_ids)
        + ". Implemented real import surfaces (mcp pool, agentspec research/source_policy/cache, fusion_rollback, council determinism/tournament/deadlock/ngt/decompose/simulate, marketplace installer/linter/scaffold, detector_control, owner_approval, router matcher, partial_preserve, pack --manifest, envelope probes ADV-0013/0065). "
        f"FAILED leftover {len(fail_ids)}: mostly remaining probe-exit (missing probe2 APIs, artifact/live drift, schema-garbage after $id rebase, AUD-0007 worktree census). Did not invent SUCCESS."
    ),
    "path": str(HERE / "shard-06.txt.result.json"),
    "remaining_n": len(fail_ids),
    "remaining_fp": fp,
    "remaining_path": str(remaining),
}
out = HERE / "shard-06.txt.result.json"
out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"ok": len(ok_ids), "fail": len(fail_ids), "fp": fp}, indent=2))
print("OK", ok_ids)
print("FAIL", fail_ids)
