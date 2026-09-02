#!/usr/bin/env python3
"""Probe 2: corrupt cache must rebuild, not serve garbage or empty (IMP-0463).

Mechanically different from probe 1 (which plants a *valid* stale package):
this probe overwrites the digest blob with truncated, zero-byte, and
bit-flipped garbage, then asserts observe() rebuilds from published source.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.package_cache import (  # noqa: E402
    ContentAddressedPackageCache,
    FIXED_MARKER,
    measure_corrupt_rebuild,
)

RECEIPT = REPO / "command-center" / "receipts" / "IMP-0463.json"
SENTINEL = "SENTINEL:IMP-0463:CACHE-CANNOT-MASK-FIX"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0463-p2-") as tmp:
        live = measure_corrupt_rebuild(Path(tmp))
        cache = ContentAddressedPackageCache(Path(tmp) / "empty-serve")
        cache.publish("demo-cache-pkg", FIXED_MARKER, "1.0.1-fixed")
        digest = cache._entry("demo-cache-pkg")["digest"]
        cache.observe("demo-cache-pkg")
        cache.corrupt_blob(digest, "empty")
        # Source still present: empty blob must rebuild, not serve empty.
        rebuilt = cache.observe("demo-cache-pkg")
        if rebuilt.payload == b"" or rebuilt.payload != FIXED_MARKER:
            print("FAILED:IMP-0463-probe2 empty blob was served as ok")
            return 1

    ok = (
        live.get("pass") is True
        and live.get("all_modes_rebuilt_to_fixed") is True
        and live.get("empty_publish_refused") is True
        and live.get("refresh_equals_fixed") is True
        and len(live.get("modes") or []) == 3
    )
    for row in live.get("modes") or []:
        if row.get("served_garbage") or row.get("served_empty") or not row.get("rebuilt"):
            ok = False
            print(f"FAILED:IMP-0463-probe2 mode {row.get('mode')} did not rebuild")
            print(json.dumps(row, sort_keys=True))
            return 1

    receipt_ok = None
    if RECEIPT.is_file() and RECEIPT.stat().st_size > 0:
        text = RECEIPT.read_text(encoding="utf-8")
        doc = json.loads(text)
        corrupt = doc.get("corrupt_cache") or {}
        receipt_ok = (
            str(doc.get("state") or "").upper()
            not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
            and SENTINEL in text
            and corrupt.get("all_modes_rebuilt_to_fixed") is True
            and corrupt.get("empty_publish_refused") is True
        )
        ok = ok and receipt_ok

    payload = {
        "probe": "probe2-corrupt-cache",
        "unit_id": "IMP-0463",
        "modes": live.get("modes"),
        "all_modes_rebuilt_to_fixed": live.get("all_modes_rebuilt_to_fixed"),
        "empty_publish_refused": live.get("empty_publish_refused"),
        "refresh_equals_fixed": live.get("refresh_equals_fixed"),
        "corrupt_detected": live.get("corrupt_detected"),
        "rebuilds": live.get("rebuilds"),
        "receipt_present": RECEIPT.is_file(),
        "receipt_ok": receipt_ok,
        "pass": ok,
    }
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    if not live.get("empty_publish_refused"):
        print("FAILED:IMP-0463-probe2 empty publish was not refused")
        return 1
    if not live.get("pass"):
        print("FAILED:IMP-0463-probe2 corrupt-cache measurement failed")
        return 1
    if receipt_ok is False:
        print("FAILED:IMP-0463-probe2 receipt corrupt_cache does not match live")
        return 1
    print(
        f"modes={len(live['modes'])} rebuilt={live['all_modes_rebuilt_to_fixed']} "
        f"empty_refused={live['empty_publish_refused']} refresh={live['refresh_equals_fixed']}"
    )
    print("SUCCESS:IMP-0463-probe2 corrupt cache rebuilds; empty is not ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
