#!/usr/bin/env python3
"""Named probe 1: both set differences re-computed from live collection output."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from reconcile import (  # noqa: E402
    BETA_ID,
    FIXTURE_SUITE,
    PLANTED_ORPHAN_ID,
    collect_and_reconcile,
)
from tests_required import test_collected_only_tests_are_enumerated  # noqa: E402
from tests_required import test_registry_only_entries_are_enumerated  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0123.json"
SUP = HERE / "fixtures" / "registry_superset.json"
SUB = HERE / "fixtures" / "registry_subset.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:TST-0123-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:TST-0123-probe1 unparseable {exc}")
        return 1
    if not isinstance(doc, dict):
        print("FAILED:TST-0123-probe1 receipt not an object")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:TST-0123-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:TST-0123" not in text:
        print("FAILED:TST-0123-probe1 sentinel absent")
        return 1
    if doc.get("unit_id") != "TST-0123":
        print(f"FAILED:TST-0123-probe1 unit_id {doc.get('unit_id')}")
        return 1

    registry_only = test_registry_only_entries_are_enumerated()
    collected_only = test_collected_only_tests_are_enumerated()
    # Re-run collector independently of the test helpers' returned blob.
    again_sup = collect_and_reconcile(FIXTURE_SUITE, SUP)
    again_sub = collect_and_reconcile(FIXTURE_SUITE, SUB)
    if PLANTED_ORPHAN_ID not in again_sup["registry_only"]["ids"]:
        print("FAILED:TST-0123-probe1 planted registry orphan not in listing-derived set")
        return 1
    if BETA_ID not in again_sub["collected_only"]["ids"]:
        print("FAILED:TST-0123-probe1 collected-only beta missing from listing-derived set")
        return 1
    if "COLLECTED " not in again_sup["listing"] or "TST-0123-COLLECT" not in again_sup["listing"]:
        print("FAILED:TST-0123-probe1 collection listing is not runner output")
        return 1
    payload = {
        "probe": "probe1-set-differences",
        "unit_id": "TST-0123",
        "registry_only_count": again_sup["registry_only"]["count"],
        "registry_only_ids": again_sup["registry_only"]["ids"],
        "collected_only_count": again_sub["collected_only"]["count"],
        "collected_only_ids": again_sub["collected_only"]["ids"],
        "collected_from_listing": again_sup["collected_ids"],
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "registry_only",
        registry_only["registry_only"]["count"],
        "collected_only",
        collected_only["collected_only"]["count"],
        "planted",
        PLANTED_ORPHAN_ID,
    )
    print("SUCCESS:TST-0123-probe1 two set differences with explicit counts from collection output")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
