#!/usr/bin/env python3
"""Named probe 2: independent re-probe of five PRESENT + live sweep honesty."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from controls import review_five_present_independent, review_ten_mappings  # noqa: E402
from controls import fixture_requirements, fixture_tests  # noqa: E402
from deliverables import sweep  # noqa: E402
from join import join  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0016.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:BLD-0016-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:BLD-0016" not in text:
        print("FAILED:BLD-0016-probe2 sentinel absent")
        return 1
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:BLD-0016-probe2 self-declared", doc.get("state"))
        return 1

    mapping_rule = doc.get("mapping_rule") or {}
    if mapping_rule.get("comment_only_counts") is not False:
        print("FAILED:BLD-0016-probe2 comment_only_counts must be false")
        return 1
    if mapping_rule.get("structural_only") is not True:
        print("FAILED:BLD-0016-probe2 structural_only must be true")
        return 1

    five = review_five_present_independent()
    matrix = review_ten_mappings(join(fixture_requirements(), fixture_tests()))
    if not five["pass"]:
        print("FAILED:BLD-0016-probe2 five-present independent re-probe")
        print(json.dumps(five, indent=2)[:3000])
        return 1
    if matrix["verdict"] != "PASS" or matrix["checked_count"] < 10:
        print("FAILED:BLD-0016-probe2 matrix reviewer")
        print(json.dumps(matrix.get("id_only"), indent=2)[:2000])
        return 1

    rec_rev = doc.get("reviewer") or {}
    if rec_rev.get("verdict") != "PASS" or rec_rev.get("checked_count", 0) < 10:
        print("FAILED:BLD-0016-probe2 receipt reviewer")
        return 1
    rec_ex = doc.get("existence_reviewer") or {}
    if rec_ex.get("verdict") != "PASS":
        print("FAILED:BLD-0016-probe2 receipt existence reviewer")
        return 1

    live = sweep()
    recorded = doc.get("deliverable_probe") or {}
    if recorded.get("source") != live["source"]:
        print("FAILED:BLD-0016-probe2 live source mismatch")
        return 1
    rec_absent = set(recorded.get("absent") or [])
    live_absent = set(live.get("absent") or [])
    if rec_absent != live_absent:
        print("FAILED:BLD-0016-probe2 absent-set mismatch", rec_absent, live_absent)
        return 1

    for row in live.get("items") or []:
        if row.get("verdict") == "PRESENT":
            if not row.get("sha256") or not row.get("bytes"):
                print("FAILED:BLD-0016-probe2 PRESENT without filesystem digest", row)
                return 1

    payload = {
        "probe": "probe2-independent-reprobe",
        "unit_id": "BLD-0016",
        "pass": True,
        "five_present": True,
        "matrix_checked": matrix["checked_count"],
        "live_absent": sorted(live_absent),
        "live_present": live.get("present"),
        "live_source": live.get("source"),
        "completeness": live.get("completeness_vs_unread_list"),
        "powershell": False,
        "second_tool": "unix-stat+sha256sum",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"five_present=True matrix={matrix['checked_count']} "
        f"absent={sorted(live_absent)} source={live.get('source')}"
    )
    print("SUCCESS:BLD-0016-probe2 independent-stat-reprobe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
