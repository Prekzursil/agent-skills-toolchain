#!/usr/bin/env python3
"""Named probe 2: collection errors are not failures and do not make a suite pass."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from harness import domain_payload, run_unittest_tree  # noqa: E402
from outcome_set import collection_errors_are_separate, counts_of  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0051-outcome-set-diff.json"
FIXTURE = HERE / "fixtures" / "collect_error"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0051-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "CNF-0051":
        print("FAILED:CNF-0051-probe2 unit_id", doc.get("unit_id"))
        return 1

    members = run_unittest_tree(FIXTURE)
    check = collection_errors_are_separate(members)
    counts = counts_of(members)
    payload = {
        "probe": "probe2-collection-error",
        "unit_id": "CNF-0051",
        "pass": bool(check["holds"]),
        "members": members,
        "counts": counts,
        "check": check,
    }
    print(json.dumps(payload, sort_keys=True))
    if not check["holds"]:
        print("FAILED:CNF-0051-probe2 collection errors were not a separate bucket")
        return 1
    if counts["collection_error"] < 1:
        print("FAILED:CNF-0051-probe2 syntax-error fixture produced no collection_error")
        return 1
    if counts["failed"] != 0:
        print("FAILED:CNF-0051-probe2 syntax error was counted as failed")
        return 1
    if counts["passed"] < 1:
        print("FAILED:CNF-0051-probe2 passing sibling was not executed")
        return 1
    if check["suite_classified_passed"]:
        print("FAILED:CNF-0051-probe2 suite with collection_error classified as passed")
        return 1
    payload = domain_payload(doc)
    live_ce = int(((payload.get("before") or {}).get("counts") or {}).get("collection_error") or 0)
    live_passed = int(((payload.get("before") or {}).get("counts") or {}).get("passed") or 0)
    if live_ce < 1:
        print("FAILED:CNF-0051-probe2 live suite was not recorded as collection_error")
        return 1
    if live_passed != 0:
        print("FAILED:CNF-0051-probe2 live uncollected suite claimed passed>0")
        return 1
    ctrl = ((payload.get("controls") or {}).get("collection_errors") or {})
    if ctrl.get("counted_separately_from_failures") is not True:
        print("FAILED:CNF-0051-probe2 artifact omitted separate-bucket proof")
        return 1
    print(
        "fixture collection_error",
        counts["collection_error"],
        "failed",
        counts["failed"],
        "passed",
        counts["passed"],
        "live_collection_error",
        live_ce,
    )
    print("SUCCESS:CNF-0051-probe2 collection errors counted separately; suite is not a pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
