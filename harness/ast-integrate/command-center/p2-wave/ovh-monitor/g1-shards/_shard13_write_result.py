#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
IDS = [
    ln.strip()
    for ln in (HERE / "shard-13.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
OK = {
    "ADV-0073",
    "ADV-0093",
    "ARC-0007",
    "AUD-0063",
    "CC-0009",
    "CNF-0026",
    "IMP-0003",
    "IMP-0030",
    "IMP-0049",
    "IMP-0067",
    "IMP-0126",
    "IMP-0183",
    "IMP-0266",
    "TST-0027",
    "TST-0098",
    "WFA-0133",
}
ok_list = [u for u in IDS if u in OK]
fail_list = [u for u in IDS if u not in OK]
rem = HERE / "shard-13.remaining.txt"
body = "\n".join(fail_list) + ("\n" if fail_list else "")
rem.write_text(body, encoding="utf-8", newline="\n")
fp = hashlib.sha256(body.encode("utf-8")).hexdigest()
attempted = len(IDS)
ok_n = len(ok_list)
fail_n = len(fail_list)
result = {
    "attempted": attempted,
    "ok": ok_n,
    "fail": fail_n,
    "verified": ok_n,
    "n": attempted,
    "shard": 13,
    "headline": (
        f"{ok_n}/{attempted} shard-13 IDs G-1 SUCCESS:delivered; "
        f"{fail_n} remain probe-exit leftover assertions"
    ),
    "summary": (
        "WSL G-1 SUCCESS:delivered "
        + " ".join(ok_list)
        + ". Implemented real import surfaces (plugin backup/projection/secret_gate, "
        "marketplace path_conflict/install/fixtures, hash_census+migration_ledger, "
        "casefold_paths, workflow_foundry consult, testinfra seed replay, "
        "test_common_core recompose). Remaining "
        + str(fail_n)
        + " are leftover probe-exit (receipt drift, schema garbage, missing probe2 APIs, "
        "eol_policy RED, ARC-0011 spread, AUD-0028 timeout). Did not invent SUCCESS:delivered. "
        "Did not git write or run global unit_manifest.py --write."
    ),
    "path": str(HERE / "shard-13.txt.result.json"),
    "remaining_n": fail_n,
    "remaining_fp": fp,
    "remaining_path": str(rem),
}
dest = HERE / "shard-13.txt.result.json"
dest.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(result, indent=2))
print("ok", ok_n, "fail", fail_n, "fp", fp)
