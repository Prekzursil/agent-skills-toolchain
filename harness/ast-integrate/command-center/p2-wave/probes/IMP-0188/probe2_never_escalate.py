#!/usr/bin/env python3
"""Named probe 2: both-states never-escalate-on-hard-case.

Good state: live predicate escalates on a hard composite and the full set PASSES.
Bad state: a progressive form that never escalates must FAIL the acceptance
checker (REJECT on correctness), not be caveated through.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fusion import (  # noqa: E402
    HARD_COMPOSITES,
    BudgetLedger,
    compose_progressive,
    evaluate,
    never_escalate_predicate,
    run_expensive,
    run_progressive,
    uncertified_predicate,
)

ART = REPO / "command-center/receipts/IMP-0188.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0188-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0188" not in text:
        return fail("sentinel-absent")

    hard_n = HARD_COMPOSITES[0]
    gold = run_expensive(hard_n, f"n={hard_n}")

    good_wf = compose_progressive(uncertified_predicate())
    good_ledger = BudgetLedger()
    good_one = run_progressive(hard_n, good_wf, good_ledger)
    good_set = evaluate(good_wf)
    if not good_one.escalated:
        return fail(f"live predicate did not escalate on hard n={hard_n}")
    if good_one.label != gold.label:
        return fail("live progressive disagrees with expensive on hard case")
    if good_set.verdict != "PASS":
        return fail(f"good-state acceptance {good_set.verdict}:{good_set.reason}")

    bad_wf = compose_progressive(never_escalate_predicate())
    bad_ledger = BudgetLedger()
    bad_one = run_progressive(hard_n, bad_wf, bad_ledger)
    bad_set = evaluate(bad_wf)
    if bad_one.escalated:
        return fail("never-escalate mutant still escalated (mutant did not take)")
    if bad_one.label == gold.label:
        return fail(
            "never-escalate on hard case matched expensive; cheap must be wrong here"
        )
    if bad_set.verdict != "REJECT":
        return fail(
            f"never-escalate was {bad_set.verdict} not REJECT (detector-failure)"
        )
    if "correctness" not in bad_set.reason:
        return fail(f"never-escalate rejected for the wrong reason:{bad_set.reason}")
    if bad_set.mismatches < 1:
        return fail("never-escalate REJECT without a counted mismatch")

    # Both-states attribution: the two workflows differ only in the predicate kind.
    if good_wf.predicate.kind == bad_wf.predicate.kind:
        return fail("good and bad predicates are not distinct")
    if good_set.verdict == bad_set.verdict:
        return fail("both-states collapsed to one verdict")

    summary = {
        "probe": "probe2-never-escalate-both-states",
        "unit_id": "IMP-0188",
        "pass": True,
        "hard_n": hard_n,
        "expensive_label": gold.label,
        "good": {
            "escalated": good_one.escalated,
            "label": good_one.label,
            "acceptance": good_set.verdict,
        },
        "bad": {
            "escalated": bad_one.escalated,
            "label": bad_one.label,
            "acceptance": bad_set.verdict,
            "reason": bad_set.reason,
            "mismatches": bad_set.mismatches,
        },
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"hard n={hard_n} good_escalated={good_one.escalated} "
        f"bad_escalated={bad_one.escalated} bad_verdict={bad_set.verdict}"
    )
    print("SUCCESS:IMP-0188-probe2 never-escalate-on-hard-case REJECT (both-states)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
