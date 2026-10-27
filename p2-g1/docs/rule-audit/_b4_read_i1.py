"""BUILD-R1: read the EXISTING _i1_ci_portability.json rather than re-measuring it."""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

GATES = {
    "rule_audit.py",
    "lazy_predict.py",
    "r2_control_count_gate.py",
    "r2_failclosed_mutation.py",
    "r2_pathrefs.py",
    "r3_corpus_parity_gate.py",
    "r4_credential_rule_gate.py",
    "r4_receipt_argv_gate.py",
}

rows = json.loads((HERE / "_i1_ci_portability.json").read_text(encoding="utf-8"))
print(f"total scripts measured by _i1: {len(rows)}")
print()
print(f"{'gate':34} {'argv':18} {'rcHOME':>6} {'rcNOHOME':>8}  drift")
seen = set()
for r in sorted(rows, key=lambda x: x["script"]):
    if r["script"] in GATES:
        seen.add(r["script"])
        drift = "DIFF" if r["rc_home"] != r["rc_nohome"] else ""
        print(
            f"{r['script']:34} {str(r['argv']):18} "
            f"{r['rc_home']:>6} {r['rc_nohome']:>8}  {drift}"
        )
missing = GATES - seen
print()
print(f"gates NOT covered by _i1: {sorted(missing) or 'none'}")
print()
print("non-gate scripts whose rc drifts across HOME states:")
for r in rows:
    if r["script"] not in GATES and r["rc_home"] != r["rc_nohome"]:
        print(f"   {r['script']}: {r['rc_home']} -> {r['rc_nohome']}")
        print(f"      nohome marker: {r['marker_nohome'][:120]}")
