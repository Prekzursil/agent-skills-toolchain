#!/usr/bin/env python3
"""Probe 2 (independent reviewer): B09-expired is STALE; third-party UNVERIFIED.

Reproduces the fabricated-run reject from a second call path. Unsupported
harness is rejected. A well-formed listing remains ACCEPTED.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.evidence_lint import (  # noqa: E402
    DECISION_ACCEPTED,
    DECISION_REJECTED,
    DECISION_STALE,
    DECISION_UNVERIFIED,
    RULE_HARNESS_UNSUPPORTED,
    RULE_RUN_UNRESOLVED,
    RULE_STALE_B09,
    RULE_THIRD_PARTY,
    ResultsLedger,
    lint_path,
)

FIXT = REPO / "tools" / "marketplace" / "tests" / "fixtures" / "evidence"
REJECTED = HERE / "fixtures" / "rejected-fabricated-run.json"


def main() -> int:
    book_path = None  # default fixture ledger
    good = lint_path(FIXT / "good-listing.json", book_path)
    stale = lint_path(FIXT / "expired-b09.json", book_path)
    third = lint_path(FIXT / "third-party.json", book_path)
    harness = lint_path(FIXT / "unsupported-harness.json", book_path)
    fabricated = lint_path(REJECTED, book_path)

    stale_ok = (
        stale.decision == DECISION_STALE
        and not stale.accepted
        and RULE_STALE_B09 in stale.rule_ids
        and stale.resolved_run_id == "run-2026-01-01-expired"
    )
    third_ok = (
        third.decision == DECISION_UNVERIFIED
        and not third.trusted
        and not third.accepted
        and RULE_THIRD_PARTY in third.rule_ids
    )
    harness_ok = (
        harness.decision == DECISION_REJECTED
        and RULE_HARNESS_UNSUPPORTED in harness.rule_ids
    )
    reproduced = (
        fabricated.decision == DECISION_REJECTED
        and RULE_RUN_UNRESOLVED in fabricated.rule_ids
    )
    good_ok = good.decision == DECISION_ACCEPTED and good.accepted and good.trusted
    ok = stale_ok and third_ok and harness_ok and reproduced and good_ok
    payload = {
        "probe": "probe2-stale-b09-and-third-party",
        "unit_id": "TST-0315",
        "pass": ok,
        "reviewer": {
            "reviewer_id": "TST-0315-probe2-stale-and-unverified",
            "independent": True,
            "verdict": "PASS" if ok else "FAIL",
        },
        "good": good.to_dict(),
        "stale_b09": stale.to_dict(),
        "third_party": third.to_dict(),
        "unsupported_harness": harness.to_dict(),
        "reproduced_fabricated_reject": fabricated.to_dict(),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not ok:
        print("FAILED:TST-0315-probe2 stale/unverified/reproduction")
        return 1
    print(
        "SUCCESS:TST-0315-probe2 B09-expired STALE not ACCEPTED; "
        "third-party UNVERIFIED not trusted; fabricated reject reproduced"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
