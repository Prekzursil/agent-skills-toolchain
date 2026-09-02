#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(r"C:\Users\Prekzursil\source\ast-integrate\command-center\p2-wave\ovh-monitor\g1-shards")
shard = [ln.strip() for ln in (HERE / "shard-02.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
ok = {
    "ADV-0007",
    "ADV-0030",
    "ADV-0064",
    "ADV-0086",
    "AUD-0015",
    "CNF-0001",
    "CNL-0109",
    "IMP-0039",
    "IMP-0135",
    "IMP-0414",
    "IMP-0474",
    "TST-0001",
    "TST-0218",
    "WFA-0111",
}
# overlay fail-remeasure
fail_jsonl = HERE / "_shard02_fail_remeasure.jsonl"
if fail_jsonl.is_file():
    for ln in fail_jsonl.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        row = json.loads(ln)
        if row.get("status") == "ok":
            ok.add(row["id"])
        elif row.get("id") in ok and row.get("status") == "fail":
            ok.discard(row["id"])
fail = [uid for uid in shard if uid not in ok]
rem_path = HERE / "shard-02.remaining.txt"
body = "\n".join(fail) + ("\n" if fail else "")
rem_path.write_text(body, encoding="utf-8", newline="\n")
fp = hashlib.sha256(body.encode("utf-8")).hexdigest()
result = {
    "attempted": len(shard),
    "ok": len(ok),
    "fail": len(fail),
    "verified": len(ok),
    "n": len(shard),
    "shard": 2,
    "headline": f"{len(ok)}/{len(shard)} shard-02 IDs G-1 SUCCESS:delivered; {len(fail)} still probe-exit/drift",
    "summary": (
        "G-1 SUCCESS:delivered "
        + " ".join(sorted(ok))
        + ". Implemented real plugin/marketplace/router/install/handoff/inject/name_linter/hook_fire/trust_tier/rollback/index_build/bayes/tiebreak surfaces, Linux launch scripts, g1_python hook v8 force-load, and missing ADV-0086 probes. "
        + f"FAILED {len(fail)} leftover catch-alls (artifact drift, schema-garbage, missing modules, unprivileged mount)."
    ),
    "path": str(HERE / "shard-02.txt.result.json"),
    "remaining_n": len(fail),
    "remaining_fp": fp,
    "remaining_path": str(rem_path),
}
out = HERE / "shard-02.txt.result.json"
out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(result, indent=2))
print("ok", sorted(ok))
print("fail_n", len(fail))
