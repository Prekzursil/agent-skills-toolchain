#!/usr/bin/env python3
"""Probe 2: known-changed, injection-as-data, reviewer http.client refetch, onion labels."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from audit import run_control_suite  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0166.json"


def main() -> int:
    bundle = run_control_suite()
    tests = bundle["tests"]
    by_id = {r["id"]: r for r in bundle["citations"]}
    ch_ok = by_id["ctrl-changed-support"]
    ch_bad = by_id["ctrl-changed-nonsupport"]
    inj = by_id["ctrl-inject"]
    onion = by_id["ctrl-onion-corroborated"]
    vendor = by_id["ctrl-vendor-529"]
    ok = (
        tests["known_changed"]["pass"] is True
        and tests["injection"]["pass"] is True
        and tests["reviewer_refetch"]["pass"] is True
        and tests["onion_label"]["pass"] is True
        and tests["http_529_no_self_throttle"]["pass"] is True
        and ch_ok["classification"] == "changed-but-still-supporting"
        and ch_bad["classification"] == "changed-and-no-longer-supporting"
        and ch_bad["support_verdict"] == "DOES-NOT-SUPPORT"
        and inj["fetched_as_data"] is True
        and not inj["tool_calls"]
        and bool(inj["instruction_shaped"])
        and onion["onion_skipped"] is True
        and float(vendor.get("slept_s") or 0) == 0
    )
    if ART.is_file() and ART.stat().st_size > 200:
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if "SUCCESS:CNF-0166" not in text:
            print("FAILED:CNF-0166-probe2 sentinel absent from receipt")
            return 1
        rt = doc.get("tests") or {}
        if rt.get("known_changed", {}).get("pass") is not True:
            print("FAILED:CNF-0166-probe2 receipt known_changed not PASS")
            return 1
        if rt.get("injection", {}).get("pass") is not True:
            print("FAILED:CNF-0166-probe2 receipt injection not PASS")
            return 1
        inj_ctl = doc.get("injection_control") or {}
        if inj_ctl.get("recorded_as_data") is not True or inj_ctl.get("tool_calls_from_fetch"):
            print("FAILED:CNF-0166-probe2 receipt injection_control")
            return 1
    print(
        f"changed_ok={ch_ok['classification']} changed_bad={ch_bad['classification']} "
        f"inject_tools={inj['tool_calls']} onion_skipped={onion['onion_skipped']} "
        f"reviewer={tests['reviewer_refetch']['pass']} vendor_slept={vendor.get('slept_s')} ok={ok}"
    )
    if not ok:
        print("FAILED:CNF-0166-probe2 changed/injection/reviewer")
        return 1
    print("SUCCESS:CNF-0166-probe2 known-changed injection reviewer onion")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
