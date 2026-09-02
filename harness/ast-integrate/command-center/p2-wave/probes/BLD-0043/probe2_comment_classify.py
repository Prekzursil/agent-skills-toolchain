#!/usr/bin/env python3
"""Named probe 2: comment-only mapping is unmapped; every orphan is classified."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from controls import (  # noqa: E402
    COMMENT_REQ,
    control_comment_only_unmapped,
    control_orphans_classified,
    review_ten_mappings,
)
from corpus import fixture_requirements, fixture_tests  # noqa: E402
from join import join  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0043.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:BLD-0043-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:BLD-0043" not in ART.read_text(encoding="utf-8"):
        print("FAILED:BLD-0043-probe2 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:BLD-0043-probe2 self-declared", doc.get("state"))
        return 1

    reqs = fixture_requirements()
    tests = fixture_tests()
    fx = join(reqs, tests)
    c_comment = control_comment_only_unmapped(reqs, tests)
    c_class = control_orphans_classified(fx)
    reviewer = review_ten_mappings(fx)

    live_orphans = doc.get("orphan_tests") or []
    live_unclass = [
        o
        for o in live_orphans
        if o.get("classification") not in {"promote", "retire"}
    ]
    live_ids = {o.get("id") for o in live_orphans}
    if len(live_ids) != len(live_orphans):
        print("FAILED:BLD-0043-probe2 duplicate live orphan ids")
        return 1

    mapping_rule = doc.get("mapping_rule") or {}
    if mapping_rule.get("comment_only_counts") is not False:
        print("FAILED:BLD-0043-probe2 comment_only_counts must be false")
        return 1
    if mapping_rule.get("structural_only") is not True:
        print("FAILED:BLD-0043-probe2 structural_only must be true")
        return 1

    if not c_comment["pass"] or not c_class["pass"]:
        print("FAILED:BLD-0043-probe2 fixture controls")
        print(json.dumps({"comment": c_comment, "classify": c_class}, indent=2)[:2000])
        return 1
    if reviewer["verdict"] != "PASS" or reviewer["checked_count"] < 10:
        print("FAILED:BLD-0043-probe2 reviewer")
        print(json.dumps(reviewer.get("id_only"), indent=2)[:2000])
        return 1
    if live_unclass:
        print("FAILED:BLD-0043-probe2 live unclassified orphans", live_unclass[:5])
        return 1
    if not live_orphans:
        print("FAILED:BLD-0043-probe2 live orphan set empty with no completeness note")
        return 1

    rec_ok = True
    rec_ids = {c.get("id") for c in (doc.get("controls") or []) if c.get("pass")}
    for needed in (c_comment["id"], c_class["id"]):
        if needed not in rec_ids:
            rec_ok = False
    if not rec_ok:
        print("FAILED:BLD-0043-probe2 receipt missing passing classify/comment controls")
        return 1

    payload = {
        "probe": "probe2-comment-classify",
        "unit_id": "BLD-0043",
        "pass": True,
        "comment_req": COMMENT_REQ,
        "comment_unmapped": True,
        "fixture_orphans_classified": True,
        "live_orphans": len(live_orphans),
        "reviewer_checked": reviewer["checked_count"],
        "reviewer_verdict": reviewer["verdict"],
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"comment_req={COMMENT_REQ} unmapped=True "
        f"orphans_classified=True reviewer={reviewer['checked_count']}"
    )
    print("SUCCESS:BLD-0043-probe2 comment-only-unmapped and orphan-classification")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
