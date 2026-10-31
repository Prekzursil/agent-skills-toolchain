"""V11: precise scoping of the audit's '156 quoted strings, 0 mismatches byte-for-byte' claim."""

import json
import subprocess
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")


def sh(*a):
    return subprocess.run(["git", *a], cwd=REPO, capture_output=True,
                          encoding="utf-8", errors="replace").stdout


cat = json.loads(sh("show", "HEAD:command-center/WORK-UNIT-CATALOG.json"))
by_id = {u["id"]: u for u in cat["work_units"]}
vs = json.loads(sh("show", "HEAD:command-center/p2-next/VENDOR-SATISFIABILITY.json"))
sg = json.loads(sh("show", "HEAD:command-center/p2-next/REVIEW-GATE-SPLIT.json"))

req_ok = req_bad = bo_ok = bo_bad = 0
bo_prefix = 0
for r in vs["units"]:
    u = by_id[r["id"]]
    rec = json.loads(sh("show", f"HEAD:{u['output_path']}"))
    real_req = str(u.get("reviewer_requirement") or "")
    real_bo = str(((rec.get("failure") or {}).get("blocked_on")) or "")
    if r["reviewer_requirement"] == real_req:
        req_ok += 1
    else:
        req_bad += 1
    if r["blocked_on"] == real_bo:
        bo_ok += 1
    else:
        bo_bad += 1
        bo_prefix += real_bo.startswith(r["blocked_on"]) and len(r["blocked_on"]) == 300
print(f"VENDOR-SATISFIABILITY reviewer_requirement : exact {req_ok}/52  mismatch {req_bad}")
print(f"VENDOR-SATISFIABILITY blocked_on           : exact {bo_ok}/52  mismatch {bo_bad}  "
      f"(of which exact 300-char prefixes: {bo_prefix})")

n = bad = 0
for bucket, rows in sg["buckets"].items():
    for r in rows:
        if "reviewer_requirement" not in r:
            continue
        n += 1
        if r["reviewer_requirement"] != str(by_id[r["id"]].get("reviewer_requirement") or ""):
            bad += 1
print(f"REVIEW-GATE-SPLIT reviewer_requirement     : compared {n}  mismatch {bad}")
print(f"\nTOTAL compared {52 + 52 + n}  TOTAL mismatches {req_bad + bo_bad + bad}  "
      f"(audit asserted 156 compared / 0 mismatches)")
print("CONTROL: the comparator discriminates -- it returns exact for "
      f"{req_ok + bo_ok + (n - bad)} of {52 + 52 + n} strings, so it is not failing universally.")
