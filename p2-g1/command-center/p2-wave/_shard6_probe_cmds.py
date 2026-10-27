#!/usr/bin/env python3
"""Extract recorded probe commands + controls from the 8 receipts."""
import json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
UIDS = [
    "BLD-0016", "BLD-0027", "BLD-0028", "BLD-0032",
    "BLD-0033", "BLD-0035", "BLD-0040", "BLD-0042",
]

for uid in UIDS:
    p = REPO / "command-center/receipts" / f"{uid}.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    print("=" * 30, uid)
    print("catalog tests_required:")
    for t in d.get("catalog_tests_required", []) or []:
        print("   catalog-req:", t[:220])
    for t in d.get("tests") or []:
        print(f"  TEST {t.get('id')} result={t.get('result')}")
        print(f"    cmd: {t.get('command')}")
    for nc in d.get("negative_controls") or []:
        print(f"  NC {nc.get('id')} fired_on_bad={nc.get('fired_on_bad_state')}")
        desc = nc.get("description") or nc.get("kind")
        print(f"    desc: {str(desc)[:240]}")
        if nc.get("bad_state_output"):
            print(f"    bad_out: {str(nc.get('bad_state_output'))[:160]}")
        if nc.get("good_state_output"):
            print(f"    good_out: {str(nc.get('good_state_output'))[:160]}")
    ext = d.get("extensions") or {}
    for k in ("named_probes", "probe1_ok", "probe2_ok"):
        if k in ext:
            v = ext[k]
            print(f"  ext.{k}: {json.dumps(v, ensure_ascii=False)[:300]}")
