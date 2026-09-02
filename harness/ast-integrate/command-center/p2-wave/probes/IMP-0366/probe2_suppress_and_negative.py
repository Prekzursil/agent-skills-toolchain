#!/usr/bin/env python3
"""IMP-0366 probe 2: settled-log suppression + two-question negative control.

Control: a question already answered in the log is suppressed even when the
claimant asserts it is unanswered.

Negative control: emit two questions; the packet check FAILS.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.owner_ask import (  # noqa: E402
    OUTCOME_EMITTED,
    OUTCOME_REFUSED_PENDING,
    OUTCOME_SUPPRESSED,
    OwnerAskSession,
    check_packet,
)

FIX = HERE / "fixtures"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0366-probe2 {msg}")
    return 1


def main() -> int:
    log_raw = json.loads((FIX / "decision_log.json").read_text(encoding="utf-8"))
    two = json.loads((FIX / "two_question_packet.json").read_text(encoding="utf-8"))
    valid = json.loads((FIX / "valid_packet.json").read_text(encoding="utf-8"))

    # Control: log has a settled answer; claimant lies that it is unanswered.
    session = OwnerAskSession(log_raw)
    settled = session.consider(
        {
            "question_id": "owner.q.ratify-a2",
            "question": "Should we ratify architecture A2 as the winning design?",
            "owner_controlled": True,
            "claimed_unanswered": True,
            "recommendation": "Re-ask because I say so.",
            "tradeoff": "Trusting the claimant avoids a log lookup.",
            "default_if_unanswered": "Ask again.",
        }
    )
    if settled.outcome != OUTCOME_SUPPRESSED:
        return fail(f"settled question not suppressed: {settled.outcome}")
    if settled.packet is not None:
        return fail("settled question produced a packet")
    if not settled.suppressed:
        return fail("suppressed flag false")
    if settled.lookup is None or not settled.lookup.settled:
        return fail("suppression without settled lookup")
    if settled.lookup.used_claimant_assertion:
        return fail("suppression used claimant assertion instead of the log")
    if settled.lookup.answer is None:
        return fail("settled lookup dropped the answer")
    if session.council_state != "RUNNING":
        return fail("suppression suspended the council")

    # Negative control: two questions in one packet must FAIL the check.
    two_check = check_packet(two)
    if two_check.ok:
        return fail("two-question packet was accepted")
    if two_check.question_count < 2:
        return fail(f"two-question count={two_check.question_count}")
    if not any("one-question-at-a-time" in e or "question-count" in e for e in two_check.errors):
        return fail(f"two-question errors did not name the rule: {two_check.errors}")

    # Session one-at-a-time: a second unanswered owner question is refused
    # while the first packet is pending.
    live = OwnerAskSession(log_raw)
    first = live.consider(
        {
            "question_id": "owner.q.evidence-tier",
            "question": valid["question"],
            "owner_controlled": True,
            "recommendation": valid["recommendation"],
            "tradeoff": valid["tradeoff"],
            "default_if_unanswered": valid["default_if_unanswered"],
        }
    )
    if first.outcome != OUTCOME_EMITTED:
        return fail(f"first unanswered failed to emit: {first.outcome}")
    second = live.consider(
        {
            "question_id": "owner.q.budget-ceiling",
            "question": "What token ceiling applies to a single council run?",
            "owner_controlled": True,
            "recommendation": "Cap at the owner's recorded ceiling.",
            "tradeoff": "No cap lets a runaway council spend the estate.",
            "default_if_unanswered": "Refuse to launch over the last recorded ceiling.",
        }
    )
    if second.outcome != OUTCOME_REFUSED_PENDING:
        return fail(f"second question not refused: {second.outcome}")
    if second.packet is not None:
        return fail("second question emitted while first pending")
    if len(live.emitted) != 1:
        return fail(f"session emitted {len(live.emitted)} packets")

    report = {
        "probe": "probe2-suppress-and-negative",
        "unit_id": "IMP-0366",
        "settled_suppressed": True,
        "claimant_assertion_ignored": True,
        "two_question_check_failed": True,
        "two_question_count": two_check.question_count,
        "two_question_errors": list(two_check.errors),
        "pending_second_refused": True,
        "pass": True,
    }
    print(json.dumps(report, sort_keys=True))
    print(
        "SUCCESS:IMP-0366-probe2 settled-suppressed two-question-FAIL "
        f"count={two_check.question_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
