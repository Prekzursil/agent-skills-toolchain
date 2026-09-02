#!/usr/bin/env python3
"""Probe 2: true-positive corpus still flags, and the receipt is a mention.

The receipt ships the forbidden patterns as examples (self-reference). A
scanner matching payload text would flag its own receipt. The rebuilt
role scanners must not. Every true-positive record must still fire —
zero FPs achieved by never firing is the wrong repair.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from evaluate import evaluate_scanners, self_scan_receipt  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0341.json"
SENTINEL = "SUCCESS:TST-0341"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def main() -> int:
    ev = evaluate_scanners()
    fx = ev["fixture"]["true_positive"]
    ct = ev["content"]["true_positive"]
    selfref = self_scan_receipt()
    print(
        json.dumps(
            {
                "probe": "probe2-true-positive-and-selfref",
                "true_positive_n": ev["true_positive_n"],
                "fixture": fx,
                "content": ct,
                "self_scan": {
                    k: selfref.get(k)
                    for k in (
                        "ok",
                        "role_fires",
                        "naive_fires",
                        "role",
                        "missing_examples",
                        "reason",
                    )
                },
            },
            sort_keys=True,
        )
    )
    if fx["n"] < 1 or ct["n"] < 1:
        print("FAILED:TST-0341-probe2 a rebuilt scanner saw an empty TP split")
        return 1
    if fx["role_silent"]:
        print(f"FAILED:TST-0341-probe2 fixture scanner missed uses {fx['role_silent_ids']}")
        return 1
    if ct["role_silent"]:
        print(f"FAILED:TST-0341-probe2 content scanner missed uses {ct['role_silent_ids']}")
        return 1
    if not fx["ok"] or not ct["ok"]:
        print("FAILED:TST-0341-probe2 true-positive corpus not fully flagged")
        return 1
    if ev.get("loosening_would_zero_tp"):
        print("FAILED:TST-0341-probe2 FP silence was bought by TP silence")
        return 1
    if not selfref.get("ok"):
        print(f"FAILED:TST-0341-probe2 self-reference {selfref}")
        return 1
    if selfref.get("role_fires"):
        print("FAILED:TST-0341-probe2 role scanner flagged its own receipt")
        return 1
    if not selfref.get("naive_fires"):
        print("FAILED:TST-0341-probe2 naive matcher did not see examples on the receipt (inert control)")
        return 1
    if not ART.is_file():
        print("FAILED:TST-0341-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        print(f"FAILED:TST-0341-probe2 self-declared {doc.get('state')}")
        return 1
    if SENTINEL not in text:
        print("FAILED:TST-0341-probe2 sentinel-absent")
        return 1
    print(
        f"fixture_tp n={fx['n']} role_fires={fx['role_fires']} silent=0 "
        f"content_tp n={ct['n']} role_fires={ct['role_fires']} silent=0 "
        f"selfref role_fires=0 naive_fires=1"
    )
    print("SUCCESS:TST-0341-probe2 true positives flagged; receipt self-scan is MENTION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
