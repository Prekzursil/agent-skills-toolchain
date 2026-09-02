#!/usr/bin/env python3
"""Probe 2: proxy-origin marker is load-bearing (negative control).

Evidence (2): artifact scan — every proxied turn carries proxy-origin.
Negative control: strip the marker; timeout silence classifies as the
same kind as an explicit human abstention. Good state is silent (scan
passes); bad state fires.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from scenario import (  # noqa: E402
    evaluate_negative_control,
    timeout_path_assigns_marker,
)

ART = REPO / "command-center" / "receipts" / "IMP-0345.json"


def main() -> int:
    neg = evaluate_negative_control()
    src = timeout_path_assigns_marker()
    receipt_ok = True
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        scan = doc.get("proxy_marker_scan") or {}
        receipt_ok = (
            "SUCCESS:IMP-0345" in text
            and scan.get("all_marked") is True
            and scan.get("proxied_count", 0) >= 1
            and scan.get("missing_marker_count") == 0
        )

    ok = (
        neg["pass"]
        and src["pass"]
        and receipt_ok
        and neg["fired_on_bad_state"]
        and neg["silent_on_good_state"]
        and neg["indistinguishable_after_strip"]
    )
    payload = {
        "probe": "probe2-marker-negative-control",
        "unit_id": "IMP-0345",
        "pass": ok,
        "negative_control": {
            "pass": neg["pass"],
            "good_kinds": neg["good_kinds"],
            "bad_kinds": neg["bad_kinds"],
            "indistinguishable_after_strip": neg["indistinguishable_after_strip"],
            "fired_on_bad_state": neg["fired_on_bad_state"],
            "silent_on_good_state": neg["silent_on_good_state"],
            "good_scan_all_marked": neg["good_scan"]["all_marked"],
            "bad_scan_missing": neg["bad_scan"]["missing_marker_count"],
        },
        "reviewer_ast": src,
        "receipt_ok": receipt_ok,
    }
    print(json.dumps(payload, sort_keys=True))
    if not ok:
        print("FAILED:IMP-0345-probe2 marker negative control")
        return 1
    print(
        "SUCCESS:IMP-0345-probe2 marker load-bearing; "
        "stripped silence indistinct from abstention"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
