#!/usr/bin/env python3
"""Named probe 1: fault-inject every component and confirm declared posture.

Signal 1: live injection outcomes (fail-open proceeds, fail-closed denies).
Signal 2: catalog receipt on disk carries SUCCESS:IMP-0053 and is not BLOCKED.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "plugin"))
sys.path.insert(0, str(REPO))

import failure_policy as FP  # noqa: E402

RECEIPT = REPO / "command-center" / "receipts" / "IMP-0053.json"


def main() -> int:
    if not RECEIPT.is_file() or RECEIPT.stat().st_size < 200:
        print("FAILED:IMP-0053-probe1 receipt missing")
        return 1
    text = RECEIPT.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0053" not in text:
        print("FAILED:IMP-0053-probe1 sentinel absent")
        return 1
    doc = json.loads(text)
    state = str(doc.get("state") or "").upper()
    if state in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:IMP-0053-probe1 self-declared {state}")
        return 1

    table = FP.load_table()
    outcomes = FP.inject_all(table)
    FP.assert_injections_match_declarations(outcomes, table)
    open_ok = [
        cid
        for cid, spec in FP.specs_from_table(table).items()
        if spec.posture == FP.FAIL_OPEN and outcomes[cid].proceed
    ]
    closed_ok = [
        cid
        for cid, spec in FP.specs_from_table(table).items()
        if spec.posture == FP.FAIL_CLOSED and outcomes[cid].denied
    ]
    report = {
        "probe": "probe1-fault-inject",
        "unit_id": "IMP-0053",
        "components": sorted(outcomes),
        "fail_open_proceeded": open_ok,
        "fail_closed_denied": closed_ok,
        "pass": True,
    }
    print(json.dumps(report, sort_keys=True))
    print(
        f"injected={len(outcomes)} fail_open={len(open_ok)} fail_closed={len(closed_ok)}"
    )
    print("SUCCESS:IMP-0053-probe1 fault injection matches declarations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
