#!/usr/bin/env python3
"""IMP-0366 probe 1: packet schema + unanswered lookup before emit.

Unit: recommendation, tradeoff and default_if_unanswered are required.
Evidence: decision-log lookup proving unanswered, then one-question assertion.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.owner_ask import (  # noqa: E402
    COUNCIL_SUSPENDED,
    OUTCOME_EMITTED,
    OUTCOME_SKIPPED_NOT_OWNER,
    OwnerAskSession,
    REQUIRED_PACKET_FIELDS,
    check_packet,
    lookup_settled,
    load_decision_log,
)

FIX = HERE / "fixtures"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0366-probe1 {msg}")
    return 1


def main() -> int:
    valid = json.loads((FIX / "valid_packet.json").read_text(encoding="utf-8"))
    log_raw = json.loads((FIX / "decision_log.json").read_text(encoding="utf-8"))
    log = load_decision_log(log_raw)

    checked = check_packet(valid)
    if not checked.ok:
        return fail(f"valid packet rejected: {checked.errors}")
    if checked.question_count != 1:
        return fail(f"valid packet question_count={checked.question_count}")
    for field in REQUIRED_PACKET_FIELDS:
        if field == "question":
            continue
        missing = dict(valid)
        missing.pop(field, None)
        if field == "tradeoff":
            missing.pop("strongest_tradeoff", None)
        if field == "default_if_unanswered":
            missing.pop("default", None)
        bad = check_packet(missing)
        if bad.ok:
            return fail(f"packet missing {field} was accepted")
        needle = field if field != "tradeoff" else "tradeoff"
        if not any(needle in e for e in bad.errors):
            return fail(f"missing {field} errors={bad.errors}")

    # Unanswered lookup is computed from the log, then emit.
    session = OwnerAskSession(log_raw)
    decision = {
        "id": "owner.q.evidence-tier",
        "question_id": "owner.q.evidence-tier",
        "question": "Should the council suspend for owner ratification of the default evidence tier?",
        "owner_controlled": True,
        "claimed_unanswered": False,  # claimant is silent/wrong; log is the source
        "recommendation": valid["recommendation"],
        "tradeoff": valid["tradeoff"],
        "default_if_unanswered": valid["default_if_unanswered"],
    }
    pre = lookup_settled(
        log, question_id=decision["question_id"], question=decision["question"]
    )
    if pre.settled:
        return fail("planted unanswered question classified settled")
    if pre.used_claimant_assertion:
        return fail("lookup used claimant assertion")
    if not pre.performed_before_emit:
        return fail("lookup not marked performed_before_emit")

    result = session.consider(decision)
    if result.outcome != OUTCOME_EMITTED:
        return fail(f"expected emit, got {result.outcome} {result.errors}")
    if result.lookup is None or result.lookup.settled:
        return fail("emit without unanswered lookup")
    if result.lookup.used_claimant_assertion:
        return fail("emit lookup used claimant assertion")
    if result.packet is None:
        return fail("emit produced no packet")
    post = check_packet(result.packet)
    if not post.ok or post.question_count != 1:
        return fail(f"emitted packet failed one-question check {post.as_dict()}")
    if result.council_state != COUNCIL_SUSPENDED or not result.suspended:
        return fail(f"council did not suspend: {result.council_state}")
    if len(session.emitted) != 1:
        return fail(f"emitted count {len(session.emitted)}")

    skip = OwnerAskSession(log_raw).consider(
        {
            "question": "Which optimiser should the compiler pick?",
            "owner_controlled": False,
            "recommendation": "none",
            "tradeoff": "none",
            "default_if_unanswered": "none",
        }
    )
    if skip.outcome != OUTCOME_SKIPPED_NOT_OWNER or skip.packet is not None:
        return fail(f"non-owner decision emitted {skip.outcome}")

    report = {
        "probe": "probe1-packet-schema",
        "unit_id": "IMP-0366",
        "valid_packet_ok": True,
        "required_fields": list(REQUIRED_PACKET_FIELDS),
        "lookup_unanswered": pre.as_dict(),
        "emit_outcome": result.outcome,
        "one_question_count": post.question_count,
        "suspended": result.suspended,
        "pass": True,
    }
    print(json.dumps(report, sort_keys=True))
    print(
        "SUCCESS:IMP-0366-probe1 packet-schema unanswered-lookup "
        f"one-question={post.question_count} suspended={result.suspended}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
