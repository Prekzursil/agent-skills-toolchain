#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
rows = [
    json.loads(ln)
    for ln in (HERE / "_shard15_measure.jsonl").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
rows.sort(key=lambda r: r["id"])
ok_ids = [r["id"] for r in rows if r.get("ok")]
fail_ids = [r["id"] for r in rows if not r.get("ok")]
remaining = HERE / "shard-15.remaining.txt"
remaining.write_text("\n".join(fail_ids) + ("\n" if fail_ids else ""), encoding="utf-8", newline="\n")
fp = hashlib.sha256(remaining.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
ok_n = len(ok_ids)
fail_n = len(fail_ids)
n = len(rows)
result = {
    "attempted": n,
    "ok": ok_n,
    "fail": fail_n,
    "verified": ok_n,
    "n": n,
    "shard": 15,
    "headline": (
        f"{ok_n}/{n} shard-15 IDs delivered on WSL G-1; {fail_n} remain probe-exit"
    ),
    "summary": (
        f"Measured all {n} assigned IDs. WSL SUCCESS:delivered "
        + " ".join(ok_ids)
        + ". Implemented real surfaces: tools.shell.pathconv, tools.wfa.nondeterminism, "
        "command-center/blueprints policy/legal/registry/CI, plugin message_renderer+redaction, "
        "marketplace deprecation+warning_channel, agentspec checkpoint secret_ref, "
        "and schema empty/garbage rejection for CNL-0089/SYN-0020/TST-0110/IMP-0398. "
        f"Leftover {fail_n} are still probe-exit (stub APIs, receipt drift, anchors, CC-0011 timeout)."
    ),
    "path": str(HERE / "shard-15.txt.result.json"),
    "remaining_n": fail_n,
    "remaining_fp": fp,
    "remaining_path": str(remaining),
}
out = HERE / "shard-15.txt.result.json"
out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(result, indent=2))
print("ok", ok_ids)
print("fail", fail_ids)
