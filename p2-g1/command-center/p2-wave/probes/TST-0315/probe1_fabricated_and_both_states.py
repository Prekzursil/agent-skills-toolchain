#!/usr/bin/env python3
"""Probe 1: fabricated run_id is rejected; both-states good listing passes.

Also: shipped evidence schema is closed (no free-text hole); a planted
holey schema is reported as an open hole; free-text evidence is rejected.
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
    HOLEY_EVIDENCE_SCHEMA,
    RULE_NOT_A_REFERENCE,
    RULE_RUN_UNRESOLVED,
    ResultsLedger,
    evidence_schema_is_closed,
    inspect_schema_holes,
    lint_listing,
    load_json,
    planted_holey_schema_holes,
)

FIXT = REPO / "tools" / "marketplace" / "tests" / "fixtures" / "evidence"
REJECTED = HERE / "fixtures" / "rejected-fabricated-run.json"


def main() -> int:
    book = ResultsLedger.load()
    closed = evidence_schema_is_closed()
    shipped_holes = inspect_schema_holes()
    holey = planted_holey_schema_holes()
    good = lint_listing(load_json(FIXT / "good-listing.json"), book)
    fabricated = lint_listing(load_json(FIXT / "fabricated-run.json"), book)
    cited = lint_listing(load_json(REJECTED), book)
    freetext = lint_listing(load_json(FIXT / "freetext-evidence.json"), book)
    extra = lint_listing(load_json(FIXT / "extra-claim.json"), book)
    holey_report = inspect_schema_holes(HOLEY_EVIDENCE_SCHEMA)

    both_states = (
        good.decision == DECISION_ACCEPTED
        and good.accepted
        and good.trusted
        and fabricated.decision == DECISION_REJECTED
        and not fabricated.accepted
        and RULE_RUN_UNRESOLVED in fabricated.rule_ids
        and cited.decision == DECISION_REJECTED
        and RULE_RUN_UNRESOLVED in cited.rule_ids
    )
    schema_ok = (
        closed
        and shipped_holes == []
        and bool(holey)
        and "evidence-type-allows-string" in holey_report
    )
    text_ok = (
        freetext.decision == DECISION_REJECTED
        and RULE_NOT_A_REFERENCE in freetext.rule_ids
        and extra.decision == DECISION_REJECTED
    )
    ok = both_states and schema_ok and text_ok
    payload = {
        "probe": "probe1-fabricated-and-both-states",
        "unit_id": "TST-0315",
        "pass": ok,
        "schema_closed": closed,
        "shipped_holes": shipped_holes,
        "planted_holey_holes": holey,
        "linter_rule": RULE_RUN_UNRESOLVED,
        "rejected_fixture": "command-center/p2-wave/probes/TST-0315/fixtures/rejected-fabricated-run.json",
        "good": good.to_dict(),
        "fabricated": fabricated.to_dict(),
        "cited_rejected": cited.to_dict(),
        "freetext": freetext.to_dict(),
        "extra_claim": extra.to_dict(),
        "both_states": both_states,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not ok:
        print("FAILED:TST-0315-probe1 fabricated reject or schema hole")
        return 1
    print(
        "SUCCESS:TST-0315-probe1 fabricated run_id rejected by "
        f"{RULE_RUN_UNRESOLVED}; both-states good listing ACCEPTED; "
        "evidence schema closed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
