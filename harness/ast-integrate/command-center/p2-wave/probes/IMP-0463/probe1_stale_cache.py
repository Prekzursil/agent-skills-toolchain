#!/usr/bin/env python3
"""Probe 1: stale cache must not mask a published fix (IMP-0463 / spec:11306).

With a cached old package present, the first observe after publish must
return the fixed bytes. The name-keyed control must still serve the stale
copy (both-states). An empty-cache run is not this probe.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.package_cache import (  # noqa: E402
    FIXED_MARKER,
    measure_stale_cache_masking,
)

RECEIPT = REPO / "command-center" / "receipts" / "IMP-0463.json"
SENTINEL = "SENTINEL:IMP-0463:CACHE-CANNOT-MASK-FIX"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0463-p1-") as tmp:
        live = measure_stale_cache_masking(Path(tmp))

    ok = (
        live.get("invocations_until_fix_observed") == 1
        and live.get("is_one") is True
        and live.get("content_addressed_observed_fix_on_first_invoke") is True
        and live.get("naive_control_still_served_stale") is True
        and live.get("both_states") is True
        and live.get("digests_differ") is True
        and live.get("old_blob_still_present") is True
    )
    receipt_ok = None
    if RECEIPT.is_file() and RECEIPT.stat().st_size > 0:
        text = RECEIPT.read_text(encoding="utf-8")
        doc = json.loads(text)
        answer = doc.get("answer") or {}
        receipt_ok = (
            str(doc.get("state") or "").upper()
            not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
            and SENTINEL in text
            and int(answer.get("invocations_until_fix_observed") or -1) == 1
            and answer.get("is_one") is True
            and (doc.get("stale_cache") or {}).get("naive_control_still_served_stale") is True
        )
        ok = ok and receipt_ok

    payload = {
        "probe": "probe1-stale-cache",
        "unit_id": "IMP-0463",
        "invocations_until_fix_observed": live.get("invocations_until_fix_observed"),
        "is_one": live.get("is_one"),
        "both_states": live.get("both_states"),
        "naive_control_still_served_stale": live.get("naive_control_still_served_stale"),
        "buggy_digest": live.get("buggy_digest"),
        "fixed_digest": live.get("fixed_digest"),
        "cache_key_fn": live.get("cache_key_fn"),
        "fixed_marker": FIXED_MARKER.decode("ascii").strip(),
        "receipt_present": RECEIPT.is_file(),
        "receipt_ok": receipt_ok,
        "pass": ok,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not live.get("naive_control_still_served_stale"):
        print("FAILED:IMP-0463-probe1 name-keyed control did not mask (detector dead)")
        return 1
    if live.get("invocations_until_fix_observed") != 1 or not live.get("is_one"):
        print(
            "FAILED:IMP-0463-probe1 invocations="
            f"{live.get('invocations_until_fix_observed')} is_one={live.get('is_one')}"
        )
        return 1
    if not live.get("both_states"):
        print("FAILED:IMP-0463-probe1 both-states failed")
        return 1
    if receipt_ok is False:
        print("FAILED:IMP-0463-probe1 receipt answer does not match live measurement")
        return 1
    print(
        f"invocations_until_fix_observed={live['invocations_until_fix_observed']} "
        f"is_one={live['is_one']} naive_masked={live['naive_control_still_served_stale']}"
    )
    print("SUCCESS:IMP-0463-probe1 stale cache cannot mask a fixed package")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
