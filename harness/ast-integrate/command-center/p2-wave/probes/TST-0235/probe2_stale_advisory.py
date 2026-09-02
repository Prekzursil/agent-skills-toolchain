#!/usr/bin/env python3
"""Probe 2: a stored advisory-DB green is not a control for today (TST-0235).

Mechanically independent from probe 1 (fresh reuse): this probe plants a
PASS from an advisory scan aged past max_age, mutates the live fixture to
carry a CVE, and requires NOT-CHECKED then an observed re-query. The naive
always-reuse control must still report PASS (detector liveness).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from gates.freshness_stamp import (  # noqa: E402
    NOT_CHECKED,
    measure_stale_advisory_green,
)

RECEIPT = REPO / "command-center" / "receipts" / "TST-0235.json"
SENTINEL = "SUCCESS:TST-0235"


def _receipt_ok() -> bool | None:
    if not RECEIPT.is_file() or RECEIPT.stat().st_size <= 0:
        return None
    text = RECEIPT.read_text(encoding="utf-8")
    doc = json.loads(text)
    answer = doc.get("answer") or {}
    stale = answer.get("stale_advisory_green") or {}
    return (
        str(doc.get("state") or "").upper()
        not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
        and SENTINEL in text
        and stale.get("before_requery_verdict") == NOT_CHECKED
        and stale.get("naive_still_pass") is True
        and stale.get("query_invoked") is True
        and int(stale.get("query_count_delta") or 0) == 1
        and stale.get("live_verdict") == "FAIL"
    )


def main() -> int:
    live = measure_stale_advisory_green()
    receipt_ok = _receipt_ok()
    ok = bool(live.get("pass")) and (receipt_ok is not False)
    payload = {
        "probe": "probe2-stale-advisory-green",
        "unit_id": "TST-0235",
        "method": "in-process-advisory-fixture",
        "data_field": "gate_verdict+query_count_delta",
        "measurement_kind": "stale-stored-green-requery",
        "pass": ok,
        "live": live,
        "receipt_present": RECEIPT.is_file(),
        "receipt_ok": receipt_ok,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if live.get("before_requery_verdict") == "PASS":
        print("FAILED:TST-0235-probe2 stale stored green was treated as PASS")
        return 1
    if not live.get("pass"):
        print("FAILED:TST-0235-probe2 stale-advisory measurement failed")
        return 1
    if live.get("before_requery_verdict") != NOT_CHECKED:
        print(
            "FAILED:TST-0235-probe2 before_requery="
            f"{live.get('before_requery_verdict')}"
        )
        return 1
    if not live.get("naive_still_pass"):
        print("FAILED:TST-0235-probe2 naive control did not stay PASS (detector dead)")
        return 1
    if not live.get("query_invoked") or int(live.get("query_count_delta") or 0) != 1:
        print("FAILED:TST-0235-probe2 re-query was not observed")
        return 1
    if live.get("live_verdict") != "FAIL":
        print("FAILED:TST-0235-probe2 live re-query did not surface today's finding")
        return 1
    if receipt_ok is False:
        print("FAILED:TST-0235-probe2 receipt does not match live stale-advisory")
        return 1
    print(
        f"before={live['before_requery_verdict']} naive={live['naive_gate_verdict']} "
        f"requery={live['query_invoked']} live={live['live_verdict']}"
    )
    print("SUCCESS:TST-0235-probe2 stored advisory green is NOT-CHECKED and re-queried")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
