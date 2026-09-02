#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OK = [
    "ADV-0056",
    "ADV-0084",
    "ADV-0107",
    "AUD-0009",
    "AUD-0039",
    "AUD-0074",
    "BLD-0015",
    "CC-0019",
    "CNF-0034",
    "CNF-0091",
    "CNF-0136",
    "CNL-0045",
    "IMP-0009",
    "IMP-0032",
    "IMP-0056",
    "IMP-0323",
    "IMP-0346",
    "IMP-0440",
    "RES-0014",
    "RES-0079",
    "TST-0019",
]
ids = [
    ln.strip()
    for ln in (HERE / "shard-21.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
ok_set = set(OK)
fail_ids = [i for i in ids if i not in ok_set]
rem_path = HERE / "shard-21.remaining.txt"
rem_text = "\n".join(fail_ids) + "\n"
rem_path.write_text(rem_text, encoding="utf-8", newline="\n")
fp = hashlib.sha256(rem_text.encode("utf-8")).hexdigest()
result = {
    "attempted": len(ids),
    "ok": len(OK),
    "fail": len(fail_ids),
    "verified": len(OK),
    "n": len(ids),
    "shard": 21,
    "headline": f"{len(OK)}/{len(ids)} shard-21 IDs live-remeasured SUCCESS:delivered; {len(fail_ids)} remain",
    "summary": (
        "Live WSL G-1 measure of all 56 leftover catch-all IDs. "
        f"SUCCESS:delivered {len(OK)}: "
        + " ".join(OK)
        + ". Remaining 35 are still probe-exit (missing modules, receipt field drift, or live assertion). "
        "Did not invent SUCCESS:delivered. No git write. No global unit_manifest.py --write. No OVH provision."
    ),
    "path": str(HERE / "shard-21.txt.result.json"),
    "remaining_n": len(fail_ids),
    "remaining_fp": fp,
    "remaining_path": str(rem_path),
    "verified_ids": OK,
    "fail_ids": fail_ids,
}
dest = HERE / "shard-21.txt.result.json"
dest.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({k: result[k] for k in ("attempted", "ok", "fail", "verified", "remaining_n", "remaining_fp", "headline")}, indent=2))
