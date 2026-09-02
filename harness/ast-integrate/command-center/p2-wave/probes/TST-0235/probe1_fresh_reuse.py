#!/usr/bin/env python3
"""Probe 1: a fresh stamped result is reused without a re-query (TST-0235).

Both-states: the same stored record aged one second past max_age must re-query.
A detector that always reuses or always re-queries fails this probe.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from gates.freshness_stamp import measure_fresh_reuse  # noqa: E402

RECEIPT = REPO / "command-center" / "receipts" / "TST-0235.json"
SENTINEL = "SUCCESS:TST-0235"


def _receipt_ok() -> bool | None:
    if not RECEIPT.is_file() or RECEIPT.stat().st_size <= 0:
        return None
    text = RECEIPT.read_text(encoding="utf-8")
    doc = json.loads(text)
    answer = doc.get("answer") or {}
    fresh = answer.get("fresh_reuse") or {}
    return (
        str(doc.get("state") or "").upper()
        not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
        and SENTINEL in text
        and fresh.get("reused") is True
        and fresh.get("query_invoked") is False
        and fresh.get("query_count_fresh") == 0
        and fresh.get("both_states") is True
    )


def main() -> int:
    live = measure_fresh_reuse()
    receipt_ok = _receipt_ok()
    ok = bool(live.get("pass")) and (receipt_ok is not False)
    payload = {
        "probe": "probe1-fresh-reuse",
        "unit_id": "TST-0235",
        "method": "injected-utc-clock",
        "data_field": "query_count_fresh+reused",
        "measurement_kind": "fresh-reuse-without-requery",
        "pass": ok,
        "live": live,
        "receipt_present": RECEIPT.is_file(),
        "receipt_ok": receipt_ok,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not live.get("pass"):
        print("FAILED:TST-0235-probe1 fresh reuse measurement failed")
        return 1
    if not live.get("reused") or live.get("query_invoked"):
        print("FAILED:TST-0235-probe1 fresh result was not reused without a re-query")
        return 1
    if live.get("query_count_fresh") != 0:
        print(f"FAILED:TST-0235-probe1 query_count_fresh={live.get('query_count_fresh')}")
        return 1
    if not live.get("both_states"):
        print("FAILED:TST-0235-probe1 both-states failed (reuse is a constant)")
        return 1
    if receipt_ok is False:
        print("FAILED:TST-0235-probe1 receipt does not match live fresh-reuse")
        return 1
    print(
        f"reused={live['reused']} query_count_fresh={live['query_count_fresh']} "
        f"stale_twin_requery={live['stale_twin_requery']}"
    )
    print("SUCCESS:TST-0235-probe1 fresh result reused without a re-query")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
