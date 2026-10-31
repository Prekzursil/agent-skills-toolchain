"""IMP-0170 probe 1 (source, mutant set): rename-invariance 20/20.

Every identifier in the workflow (workflow id, stage ids, tool instance
ids, titles) is renamed under 20 deterministic schemes. The structural
mechanism fingerprint must be EQUAL for 20/20 mutants. The probe also
proves the renames are real (each mutant differs from the base as a dict).

Exit 0 iff 20/20 hold.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import fingerprint  # noqa: E402
import workflows_lib as WL  # noqa: E402

base = WL.base_workflow()
base_fp = fingerprint.fingerprint(base)

rows = []
all_equal = True
for tag in WL.TAGS:
    mutant = WL.rename_mutant(base, tag)
    really_renamed = mutant != base and mutant["stages"][0]["id"] != base["stages"][0]["id"]
    fp = fingerprint.fingerprint(mutant)
    equal = fp == base_fp
    all_equal = all_equal and equal and really_renamed
    rows.append({"tag": tag, "equal": equal, "really_renamed": really_renamed, "sha256": fp})

checks = {
    "count_20": len(rows) == 20,
    "all_equal": all_equal,
    "renames_real": all(r["really_renamed"] for r in rows),
    "base_fingerprint_stable": fingerprint.fingerprint(WL.base_workflow()) == base_fp,
}

result = {
    "probe": "probe1-rename-invariance",
    "unit_id": "IMP-0170",
    "base_sha256": base_fp,
    "count": str(sum(1 for r in rows if r["equal"])) + "/20",
    "checks": checks,
    "rows": rows,
    "pass": all(checks.values()),
}
print(json.dumps(result, sort_keys=True))
if not result["pass"]:
    print("FAILED:IMP-0170-probe1 " + ",".join(k for k, v in checks.items() if not v))
    raise SystemExit(1)
print("SUCCESS:IMP-0170-probe1 rename-invariance 20/20 base=" + base_fp[:16])
