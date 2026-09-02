#!/usr/bin/env python3
"""Probe 1: a published score must carry exclusion_count (even when zero).

Catalog test: test_score_is_published_with_the_exclusion_count.
A score with the count omitted is an overclaim and must be rejected.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from policy import TEST_SCORE_WITH_COUNT  # noqa: E402
from schema_local import payload  # noqa: E402
from triage import (  # noqa: E402
    OVERCLAIM,
    check_published_record,
    detector_controls,
    proposed_exclusions,
    publish_score,
)

ART = REPO / "command-center/receipts/TST-0120.json"
UID = "TST-0120"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0120-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != UID:
        return fail(f"unit_id {doc.get('unit_id')}")
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:TST-0120" not in text:
        return fail("sentinel-absent")

    body = payload(doc)
    score = body.get("score") or {}
    if "exclusion_count" not in score:
        return fail("artifact score missing exclusion_count")
    if score.get("mutation_score") is None:
        return fail("artifact mutation_score missing")
    if score.get("exclusion_count") != len(body.get("exclusions") or []):
        return fail("artifact exclusion_count != len(exclusions)")

    ctrl = detector_controls()
    live = ctrl["clean"]
    if live.get("exclusion_count") != score.get("exclusion_count"):
        return fail(
            f"live exclusion_count {live.get('exclusion_count')} "
            f"!= artifact {score.get('exclusion_count')}"
        )
    if live.get("mutation_score") != score.get("mutation_score"):
        return fail("live mutation_score != artifact")
    if not live.get("accepted"):
        return fail("live clean score not accepted")

    omitted = ctrl["planted"]["score_without_exclusion_count"]
    if omitted["accepted"] or OVERCLAIM not in omitted["errors"]:
        return fail("omitted exclusion_count was not rejected as overclaim")

    measured = ctrl["measured"]
    zero = publish_score(measured, [])
    if "exclusion_count" not in zero:
        return fail("zero-exclusion publish omitted exclusion_count")
    if zero["exclusion_count"] != 0:
        return fail(f"zero-exclusion count {zero['exclusion_count']}")
    if not zero["accepted"]:
        return fail(f"zero-exclusion rejected {zero['errors']}")
    if zero["killed"] != 4 or zero["total"] != 7:
        return fail(f"zero-exclusion killed/total {zero['killed']}/{zero['total']}")
    if abs((zero["mutation_score"] or 0) - (4 / 7)) > 1e-12:
        return fail(f"zero-exclusion score {zero['mutation_score']}")

    mismatched = publish_score(
        measured,
        proposed_exclusions(measured, ctrl["clean"]["exclusions"][0]["reviewer_id"]),
        override_exclusion_count=0,
    )
    if mismatched["accepted"]:
        return fail("mismatched exclusion_count was accepted")
    if "overclaim:exclusion-count-mismatch" not in " ".join(mismatched["errors"]):
        return fail(f"mismatch errors {mismatched['errors']}")

    rec_errs = check_published_record(live)
    if rec_errs:
        return fail(f"clean record check {rec_errs}")

    summary = {
        "probe": "probe1-score-published-with-exclusion-count",
        "unit_id": UID,
        "test": TEST_SCORE_WITH_COUNT,
        "pass": True,
        "exclusion_count": live["exclusion_count"],
        "mutation_score": live["mutation_score"],
        "overclaim_rejected": True,
        "zero_exclusion_count_published": True,
        "mismatch_rejected": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"exclusion_count={live['exclusion_count']} "
        f"score={live['mutation_score']} overclaim_rejected=True"
    )
    print("SUCCESS:TST-0120-probe1 score published with exclusion count")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
