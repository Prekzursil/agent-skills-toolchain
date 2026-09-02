#!/usr/bin/env python3
"""Named probe 2: bill-minus-shipped phantom plus clean both-empty.

Mechanically different axis from probe 1. Also asserts walked depth and the
NOT-CHECKED peer the resolver refused to invent.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/REL-0011.json"


def main() -> int:
    p = S.control_phantom()
    c = S.control_clean()
    print(json.dumps({"phantom": p, "clean_counts": c.get("counts"),
                      "walked_depth": c.get("walked_depth"),
                      "not_checked": c.get("not_checked")}, indent=2, default=str)[:4000])
    if not p.get("pass"):
        print("FAILED:REL-0011-probe2 phantom did not fire bill-minus-shipped")
        return 1
    if S.PHANTOM_PURL not in (p.get("bill_minus_shipped") or []):
        print("FAILED:REL-0011-probe2 phantom purl missing")
        return 1
    if not c.get("pass"):
        print("FAILED:REL-0011-probe2 clean build was not both-empty with depth")
        return 1
    if int(c.get("walked_depth") or 0) < 3:
        print(f"FAILED:REL-0011-probe2 walked_depth={c.get('walked_depth')} want>=3")
        return 1
    nc_names = [str(x.get("name")) for x in (c.get("not_checked") or [])]
    if "unresolved-peer" not in nc_names:
        print(f"FAILED:REL-0011-probe2 unresolved-peer not NOT-CHECKED: {nc_names}")
        return 1
    if (c.get("counts") or {}).get("bill", 0) < 6:
        print(f"FAILED:REL-0011-probe2 clean bill too small {c.get('counts')}")
        return 1

    if not ART.is_file():
        print("FAILED:REL-0011-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:REL-0011" not in text:
        print("FAILED:REL-0011-probe2 sentinel absent")
        return 1
    diffs = doc.get("diffs") or {}
    counts = diffs.get("counts") or {}
    if int(counts.get("closure_minus_bill", 1)) != 0:
        print("FAILED:REL-0011-probe2 receipt clean closure-minus-bill not empty")
        return 1
    if int(counts.get("bill_minus_shipped", 1)) != 0:
        print("FAILED:REL-0011-probe2 receipt clean bill-minus-shipped not empty")
        return 1
    if int(doc.get("walked_depth") or 0) != int(c.get("walked_depth") or -1):
        print("FAILED:REL-0011-probe2 receipt walked_depth drifted from live clean")
        return 1
    live_bill = set(c.get("bill") or [])
    rec_bill = set((diffs.get("bill") or []))
    if live_bill != rec_bill:
        print("FAILED:REL-0011-probe2 receipt bill set drifted from live clean")
        print(f"  only_live={sorted(live_bill - rec_bill)}")
        print(f"  only_receipt={sorted(rec_bill - live_bill)}")
        return 1
    other = doc.get("reviewer", {}).get("other_vendor_human_review")
    if other and other != "NOT-CHECKED":
        print("FAILED:REL-0011-probe2 overclaimed other-vendor reviewer")
        return 1
    print(
        f"phantom_hit={p['hit']} clean_bill={counts.get('bill')} "
        f"walked_depth={c['walked_depth']} not_checked={nc_names}"
    )
    print("SUCCESS:REL-0011-probe2 phantom-and-clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
