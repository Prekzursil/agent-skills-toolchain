#!/usr/bin/env python3
"""Named probe 1: write-API byte-exact round trip + static scan of tools/.

Also checks the catalog receipt carries SUCCESS:TST-0189 and matching sha256.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from contract import (  # noqa: E402
    RECEIPT,
    SENTINEL,
    UNIT_ID,
    assert_pass,
    intended_sha256,
    load_receipt,
    measure,
)


def main() -> int:
    ev = measure()
    errors = assert_pass(ev)
    if errors:
        print(f"FAILED:{UNIT_ID}-probe1 {errors}")
        print(json.dumps(ev, indent=2, default=str)[:4000])
        return 1

    doc = load_receipt()
    text = RECEIPT.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print(f"FAILED:{UNIT_ID}-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:{UNIT_ID}-probe1 self-declared {doc.get('state')}")
        return 1
    if doc.get("unit_id") != UNIT_ID and doc.get("id") != UNIT_ID:
        print(f"FAILED:{UNIT_ID}-probe1 receipt id mismatch")
        return 1
    evidence = doc.get("evidence") or {}
    if evidence.get("intended_sha256") != intended_sha256():
        print("FAILED:TST-0189-probe1 receipt intended_sha256 drifted from payload")
        return 1
    if evidence.get("landed_sha256") != ev["write_api"]["landed_sha256"]:
        print("FAILED:TST-0189-probe1 receipt landed_sha256 drifted from live write API")
        return 1
    if not evidence.get("write_api_sha256_match"):
        print("FAILED:TST-0189-probe1 receipt write_api_sha256_match is not true")
        return 1
    if evidence.get("static_scan_here_string_file_create_sites") != 0:
        print("FAILED:TST-0189-probe1 receipt static scan not zero")
        return 1
    if ev["static_scan"]["here_string_file_create_sites"] != 0:
        print("FAILED:TST-0189-probe1 live static scan not zero")
        return 1
    if not ev["write_api"]["round_trip_exact"]:
        print("FAILED:TST-0189-probe1 live round-trip failed")
        return 1

    print(
        json.dumps(
            {
                "probe": "probe1-write-api-roundtrip",
                "unit_id": UNIT_ID,
                "round_trip_exact": True,
                "sha256": ev["intended_sha256"],
                "here_string_sites": 0,
            },
            sort_keys=True,
        )
    )
    print(f"SUCCESS:{UNIT_ID}-probe1 write-API round-trip and zero here-string file-create sites")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
