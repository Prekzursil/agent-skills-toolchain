#!/usr/bin/env python3
"""Named probe 1: obligation lifecycle including expiry and escalation.

Does not read the author's summary. Exercises the public SocraticProtocol
surface: ask, record_turn, age, expire, escalate, discharge.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.protocol.socratic import (  # noqa: E402
    STATE_DISCHARGED,
    STATE_ESCALATED,
    STATE_EXPIRED,
    STATE_OPEN,
    SocraticProtocol,
    ledger_digest,
)

MODULE = REPO / "tools/council/protocol/socratic.py"
LEDGER_OUT = HERE / "obligation-ledger.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0292-probe1 {msg}")
    return 1


def main() -> int:
    if not MODULE.is_file() or MODULE.stat().st_size < 200:
        return fail("socratic.py missing")

    src = MODULE.read_text(encoding="utf-8")
    if "naive_any_bytes_discharge" not in src:
        return fail("defeated byte-count control not present for comparison")

    # --- genuine discharge ---
    p = SocraticProtocol(default_due_in_turns=3, auto_escalate=False)
    ob = p.ask("alice", "bob", "Does an empty reply discharge a socratic obligation?")
    if ob.state != STATE_OPEN or ob.age_turns != 0:
        return fail(f"fresh obligation not OPEN/age0: {ob.state} {ob.age_turns}")
    p.record_turn("carol", "unrelated seating remark about weather")
    if p.get(ob.id).state != STATE_OPEN or p.get(ob.id).age_turns != 1:
        return fail("wrong-speaker turn must age but not discharge")
    p.record_turn(
        "bob",
        "No. Empty replies remain OPEN; discharge requires addressing the question.",
    )
    discharged = p.get(ob.id)
    if discharged.state != STATE_DISCHARGED:
        return fail(f"substantive answer did not discharge: {discharged.state} {discharged.last_reason}")
    if discharged.age_turns != 2 or discharged.discharged_turn != 2:
        return fail(f"discharge age/turn wrong: age={discharged.age_turns} at={discharged.discharged_turn}")

    # --- non-answer then expiry ---
    q = SocraticProtocol(default_due_in_turns=3, auto_escalate=False)
    target = q.ask(
        "alice",
        "bob",
        "What is the SHA-256 of the empty string?",
        due_in_turns=3,
    )
    q.record_turn("alice", "waiting")
    q.record_turn("bob", "ok" + (" " * 4000))
    still = q.get(target.id)
    if still.state != STATE_OPEN:
        return fail(f"padded non-answer discharged: {still.state} {still.last_reason}")
    if still.age_turns != 2:
        return fail(f"age after two turns want 2 got {still.age_turns}")
    q.record_turn("carol", "still waiting on bob")
    expired = q.get(target.id)
    if expired.state != STATE_EXPIRED:
        return fail(f"deadline miss did not expire: {expired.state} age={expired.age_turns}")
    if expired.expired_turn != 3 or expired.age_turns != 3:
        return fail(f"expiry metadata wrong turn={expired.expired_turn} age={expired.age_turns}")

    follow = q.escalate(target.id)
    escalated = q.get(target.id)
    if escalated.state != STATE_ESCALATED:
        return fail(f"escalate did not mark ESCALATED: {escalated.state}")
    if follow.kind != "escalation" or follow.parent_id != target.id:
        return fail("follow-up is not an escalation of the expired obligation")
    if follow.state != STATE_OPEN or follow.due_in_turns != 1:
        return fail("escalation follow-up must be OPEN with due_in_turns=1")
    if follow.addressee != "bob":
        return fail("escalation must re-oblige the original addressee")

    # deadline-turn answer still discharges (age == due)
    r = SocraticProtocol(default_due_in_turns=2, auto_escalate=False)
    late = r.ask("alice", "bob", "Does an empty reply discharge a socratic obligation?", due_in_turns=2)
    r.record_turn("carol", "nudge")
    r.record_turn("bob", "No.")
    if r.get(late.id).state != STATE_DISCHARGED:
        return fail("answer on the due turn must still discharge")

    # auto-escalate on silence
    s = SocraticProtocol(default_due_in_turns=1, auto_escalate=True)
    auto = s.ask("alice", "bob", "How many open obligations remain after a non-answer?")
    s.record_turn("carol", "clock tick")
    if s.get(auto.id).state != STATE_ESCALATED:
        return fail(f"auto-escalate did not fire: {s.get(auto.id).state}")
    if len(s.by_state(STATE_OPEN)) != 1:
        return fail("auto-escalate must leave exactly one OPEN follow-up")

    rows = q.ledger()
    states = {row["state"] for row in rows}
    if not {STATE_ESCALATED, STATE_OPEN} <= states:
        return fail(f"ledger missing expected states: {states}")
    ages = [row["age_turns"] for row in rows]
    if any(a < 0 for a in ages):
        return fail("negative age in ledger")

    payload = {
        "probe": "probe1-lifecycle",
        "unit_id": "IMP-0292",
        "pass": True,
        "ledger_digest": ledger_digest(rows),
        "states_present": sorted(states),
        "open": sum(1 for row in rows if row["state"] == STATE_OPEN),
        "discharged_in_first_session": True,
        "expired_then_escalated": True,
        "padded_non_answer_remained_open": True,
        "wrong_speaker_cannot_discharge": True,
        "deadline_turn_discharge": True,
        "auto_escalate": True,
        "ledger": rows,
    }
    LEDGER_OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in payload.items() if k != "ledger"}, sort_keys=True))
    print("SUCCESS:IMP-0292-probe1 obligation lifecycle including expiry and escalation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
