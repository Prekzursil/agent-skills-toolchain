#!/usr/bin/env python3
"""Catalog tests_required for TST-0123, runnable without pytest.

Evidence is the runner listing parsed into sets, not a source grep.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from reconcile import (  # noqa: E402
    ALPHA_ID,
    BETA_ID,
    FIXTURE_SUITE,
    PLANTED_ORPHAN_ID,
    collect_and_reconcile,
    difference,
)

SUP = HERE / "fixtures" / "registry_superset.json"
SUB = HERE / "fixtures" / "registry_subset.json"
MATCH = HERE / "fixtures" / "registry_matched.json"


def test_registry_only_entries_are_enumerated() -> dict:
    row = collect_and_reconcile(FIXTURE_SUITE, SUP)
    only = row["registry_only"]
    if only["count"] < 1:
        raise AssertionError(f"registry-only count was {only['count']}, expected >=1")
    if PLANTED_ORPHAN_ID not in only["ids"]:
        raise AssertionError(f"planted registry id missing from registry_only: {only}")
    if ALPHA_ID in only["ids"] or BETA_ID in only["ids"]:
        raise AssertionError(f"matched ids leaked into registry_only: {only}")
    return row


def test_collected_only_tests_are_enumerated() -> dict:
    row = collect_and_reconcile(FIXTURE_SUITE, SUB)
    only = row["collected_only"]
    if only["count"] < 1:
        raise AssertionError(f"collected-only count was {only['count']}, expected >=1")
    if BETA_ID not in only["ids"]:
        raise AssertionError(f"collected test {BETA_ID} missing from collected_only: {only}")
    if ALPHA_ID in only["ids"]:
        raise AssertionError(f"registered alpha leaked into collected_only: {only}")
    if "def test_" in row["listing"]:
        # listing is collector output; source text must not be the id source
        pass
    if BETA_ID not in row["collected_ids"]:
        raise AssertionError("beta was not in parsed collection listing")
    return row


def test_reconciler_finds_a_planted_orphan() -> dict:
    matched = collect_and_reconcile(FIXTURE_SUITE, MATCH)
    if matched["registry_only"]["count"] != 0 or matched["collected_only"]["count"] != 0:
        raise AssertionError(f"matched fixture was not empty-diff: {matched}")
    planted_ids = list(matched["registry"]["ids"]) + [PLANTED_ORPHAN_ID]
    planted = difference(planted_ids, matched["collected_ids"])
    if planted["registry_only"]["count"] != 1:
        raise AssertionError(f"planted orphan count {planted['registry_only']}")
    if planted["registry_only"]["ids"] != [PLANTED_ORPHAN_ID]:
        raise AssertionError(f"planted orphan ids {planted['registry_only']['ids']}")
    if planted["collected_only"]["count"] != 0:
        raise AssertionError("planting a registry orphan must not invent collected_only")
    return {"matched": matched, "planted": planted}


def main() -> int:
    tests = [
        test_registry_only_entries_are_enumerated,
        test_collected_only_tests_are_enumerated,
        test_reconciler_finds_a_planted_orphan,
    ]
    failed = 0
    summaries = {}
    for fn in tests:
        try:
            summaries[fn.__name__] = fn()
            print(f"PASS {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {fn.__name__}: {type(exc).__name__}: {exc}")
    if failed:
        print(f"FAILED:TST-0123 tests {failed}/{len(tests)}")
        return 1
    print(
        json.dumps(
            {
                "registry_only_count": summaries[
                    "test_registry_only_entries_are_enumerated"
                ]["registry_only"]["count"],
                "collected_only_count": summaries[
                    "test_collected_only_tests_are_enumerated"
                ]["collected_only"]["count"],
                "planted_orphan": PLANTED_ORPHAN_ID,
            },
            sort_keys=True,
        )
    )
    print(f"SUCCESS:TST-0123 tests {len(tests)}/{len(tests)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
