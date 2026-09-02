#!/usr/bin/env python3
"""Probe 1: catalog tests_required for TST-0008.

Role checker must FAIL a body-only mention, PASS a status-field use, and
FAIL a different unit id (naming the mismatch). The substring cousin must
PASS the two mention-containing fixtures, proving the detectors disagree.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sentinel_check as C  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:TST-0008-probe1 {msg}")
    return 1


def main() -> int:
    campaign = C.run_required_tests()
    print(json.dumps({"campaign": campaign}, sort_keys=True, default=str))
    if campaign["n"] != 3:
        return fail(f"expected 3 tests, got {campaign['n']}")
    by_id = {row["id"]: row for row in campaign["tests"]}
    for name in (
        "test_sentinel_in_body_does_not_satisfy",
        "test_sentinel_in_status_field_satisfies",
        "test_sentinel_of_a_DIFFERENT_unit_id_does_not_satisfy",
    ):
        row = by_id.get(name)
        if row is None:
            return fail(f"missing {name}")
        print(f"{name} ok={row['ok']} role_satisfies={row['role']['satisfies']}")
        if row["ok"] is not True:
            return fail(name)

    body = by_id["test_sentinel_in_body_does_not_satisfy"]
    if body["substring_cousin"]["satisfies"] is not True:
        return fail("substring cousin silent on body-mention fixture")
    if body["role"]["satisfies"] is not False:
        return fail("role checker accepted body mention")

    use = by_id["test_sentinel_in_status_field_satisfies"]
    if use["whole_field_equals_expected"] is not False:
        return fail("status fixture was not multiline; terminal-line not stressed")

    wrong = by_id["test_sentinel_of_a_DIFFERENT_unit_id_does_not_satisfy"]
    if "TST-0017" not in str(wrong["role"].get("mismatch") or ""):
        return fail("wrong-id diagnostic omitted observed TST-0017")
    if wrong["substring_cousin"]["satisfies"] is not True:
        return fail("substring cousin silent on wrong-id body quote")

    if campaign["ok"] is not True:
        return fail("campaign ok flag false")
    print("SUCCESS:TST-0008-probe1 role vs substring; body mention fails")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
