#!/usr/bin/env python3
"""Probe 2: independent reviewer fifth mutant + live receipt reviewer PASS.

Mechanically different from probe 1: does not re-run the four catalog mutants.
Applies a fabricated artifact sha256 the authoring four-mutant set does not
contain, after schema required-fields were frozen.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center"))

import receipt_validate as V  # noqa: E402

RECEIPT = REPO / "command-center" / "receipts" / "CC-0002.json"


def main() -> int:
    if not RECEIPT.is_file():
        print("FAILED:CC-0002-probe2 live receipt absent")
        return 1
    live = json.loads(RECEIPT.read_text(encoding="utf-8"))
    if "SUCCESS:CC-0002" not in RECEIPT.read_text(encoding="utf-8"):
        print("FAILED:CC-0002-probe2 sentinel absent")
        return 1

    golden_v, _, _ = V.admit_doc(live, REPO)
    fifth = V.mutant_m5_fabricated_digest(live)
    fv, fc, fr = V.admit_doc(fifth, REPO)
    summary = {
        "fifth_class": "fabricated-artifact-digest",
        "fifth_verdict": fv,
        "fifth_codes": fc,
        "fifth_caught": fv == "REJECT" and "C5" in fc,
        "fifth_not_a_catalog_four": not set(fc) <= {"C1", "C2", "C3"},
        "golden_still_accept": golden_v == "ACCEPT",
        "reason": fr[0] if fr else "",
    }
    print(json.dumps(summary, sort_keys=True))

    if golden_v != "ACCEPT":
        print("FAILED:CC-0002-probe2 golden no longer ACCEPT")
        return 1
    if not summary["fifth_caught"]:
        print("FAILED:CC-0002-probe2 fifth mutant not caught on C5", summary)
        return 1
    if "C5" not in fc:
        print("FAILED:CC-0002-probe2 fifth collapsed into C1/C2/C3")
        return 1

    # Confirm the four catalog mutants still would not be this payload:
    # fabricated digest keeps completion_sentinel, non-empty evidence, catalog
    # unit_id, and parseable JSON.
    if "completion_sentinel" not in fifth:
        print("FAILED:CC-0002-probe2 fifth accidentally dropped completion_sentinel")
        return 1
    if not fifth.get("evidence"):
        print("FAILED:CC-0002-probe2 fifth accidentally emptied evidence")
        return 1
    if fifth.get("unit_id") not in V.catalog_ids(REPO):
        print("FAILED:CC-0002-probe2 fifth is just m3")
        return 1

    rev = live.get("reviewer") or {}
    if rev.get("verdict") != "PASS" or not rev.get("independent"):
        print("FAILED:CC-0002-probe2 receipt reviewer not independent PASS")
        return 1
    rec_fifth = live.get("reviewer_fifth_mutant") or {}
    if rec_fifth.get("class") != "fabricated-artifact-digest":
        print("FAILED:CC-0002-probe2 receipt fifth class drift")
        return 1
    if rec_fifth.get("caught") is not True:
        print("FAILED:CC-0002-probe2 receipt fifth not marked caught")
        return 1

    print("SUCCESS:CC-0002-probe2 fifth-mutant-caught independent-reviewer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
