#!/usr/bin/env python3
"""Named probe 2: prior records cannot be edited or deleted.

Signal 2 of the catalog evidence requirement. The refusal is itself logged.
Negative control: resolution without a recorded dispute opportunity is refused.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.event_log import ImmutableRecordError  # noqa: E402
from marketplace.moderation import (  # noqa: E402
    DISPUTE_BODY_FIXTURE,
    MUTATION_REFUSED,
    REPORT_BODY_FIXTURE,
    RESOLVE_REFUSED,
    DisputeOpportunityRequired,
    ModerationQueue,
    run_full_cycle,
)

RECEIPT = REPO / "command-center/receipts/IMP-0110.json"
SENTINEL = "SUCCESS:IMP-0110"


def _check_receipt() -> None:
    if not RECEIPT.is_file() or RECEIPT.stat().st_size < 200:
        raise SystemExit("FAILED:IMP-0110-probe2 receipt missing")
    text = RECEIPT.read_text(encoding="utf-8")
    if SENTINEL not in text:
        raise SystemExit("FAILED:IMP-0110-probe2 sentinel absent")
    doc = json.loads(text)
    state = str(doc.get("state") or "").upper()
    if state in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        raise SystemExit(f"FAILED:IMP-0110-probe2 self-declared:{state}")


def main() -> int:
    _check_receipt()
    q = ModerationQueue()
    result = run_full_cycle(q)
    rid = result["report_id"]
    seq0 = result["events"][0]["seq"]
    ops = []
    for label, fn in (
        ("edit_report", lambda: q.try_edit_report(rid, "hacked", actor_id="attacker")),
        ("delete_report", lambda: q.try_delete_report(rid, actor_id="attacker")),
        ("edit_dispute", lambda: q.try_edit_dispute(rid, "hacked", actor_id="attacker")),
        ("rewrite_event", lambda: q.log.try_rewrite(seq0, {"body": "forged"}, actor_id="attacker")),
        ("delete_event", lambda: q.log.try_delete(seq0, actor_id="attacker")),
    ):
        try:
            fn()
            print(f"FAILED:IMP-0110-probe2 {label} was not refused")
            return 1
        except ImmutableRecordError:
            ops.append(label)

    audit = q.audit(rid)
    if audit["report"]["body"] != REPORT_BODY_FIXTURE:
        print("FAILED:IMP-0110-probe2 report body mutated")
        return 1
    if audit["dispute"]["body"] != DISPUTE_BODY_FIXTURE:
        print("FAILED:IMP-0110-probe2 dispute body mutated")
        return 1
    refusals = [e for e in q.log.events() if e["event_type"] == MUTATION_REFUSED]
    if len(refusals) < 5:
        print("FAILED:IMP-0110-probe2 refusals not logged", len(refusals))
        return 1

    neg = ModerationQueue()
    filed = neg.file_report(
        package_id="acme.widget",
        category="spam",
        reporter_id="user:reporter-1",
        body="unsolicited advertising",
    )
    refused = False
    try:
        neg.resolve(
            filed["report_id"],
            outcome="upheld",
            actor_id="moderator:queue",
            rationale="skip the publisher",
        )
    except DisputeOpportunityRequired as exc:
        refused = True
        if exc.refusal.get("event_type") != RESOLVE_REFUSED:
            print("FAILED:IMP-0110-probe2 negative control not logged")
            return 1
    if not refused:
        print("FAILED:IMP-0110-probe2 negative control did not refuse")
        return 1
    if neg.audit(filed["report_id"])["state"] != "filed":
        print("FAILED:IMP-0110-probe2 negative control changed state")
        return 1

    q.log.verify_chain()
    payload = {
        "pass": True,
        "probe": "probe2-immutability",
        "unit_id": "IMP-0110",
        "refused_ops": ops,
        "refusals_logged": len(refusals),
        "bodies_unchanged": True,
        "negative_control_refused": True,
        "reviewer_both_texts_retained": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "refused="
        + ",".join(ops)
        + " negative_control_refused=True both_texts_retained=True"
    )
    print("SUCCESS:IMP-0110-probe2 prior records immutable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
