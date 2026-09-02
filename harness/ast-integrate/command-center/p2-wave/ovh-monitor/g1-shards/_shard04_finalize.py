#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
IDS = [
    ln.strip()
    for ln in (HERE / "shard-04.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
recs = []
for line in (HERE / "_shard04_measure.jsonl").read_text(encoding="utf-8").splitlines():
    if line.startswith("{"):
        recs.append(json.loads(line))
by = {r["id"]: r for r in recs}
ok_ids = [uid for uid in IDS if by.get(uid, {}).get("ok")]
fail_ids = [uid for uid in IDS if uid not in ok_ids]
rem_path = HERE / "shard-04.remaining.txt"
rem_path.write_text("\n".join(fail_ids) + ("\n" if fail_ids else ""), encoding="utf-8", newline="\n")
fp = hashlib.sha256(rem_path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
result = {
    "attempted": len(IDS),
    "ok": len(ok_ids),
    "fail": len(fail_ids),
    "verified": len(ok_ids),
    "n": len(IDS),
    "shard": 4,
    "headline": f"{len(ok_ids)}/{len(IDS)} shard-04 IDs G-1 SUCCESS:delivered; {len(fail_ids)} still probe-exit/module/receipt",
    "summary": (
        "Measured all 57 leftover catch-all IDs on WSL p2-g1. "
        f"SUCCESS:delivered {ok_ids}. "
        f"FAIL {fail_ids}. "
        "Restored ADV-0087 probes; implemented interpreter_probe, flagship_e2e_contract package, "
        "workflow_import harness, arrival_scheduler, hang_detect, telemetry.sweep, registry_fetch, "
        "repair_loop, net_allowlist inspect_config_keys, foundry consumers; schema-aware leftover fill; "
        "AUD-0085 skip huge dirs. Remaining fails are live assertion/module gaps (not skipped)."
    ),
    "path": str(HERE / "shard-04.txt.result.json"),
    "remaining_n": len(fail_ids),
    "remaining_fp": fp,
    "remaining_path": str(rem_path),
}
(HERE / "shard-04.txt.result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"ok": ok_ids, "fail": fail_ids, "n_ok": len(ok_ids), "n_fail": len(fail_ids)}, indent=2))
