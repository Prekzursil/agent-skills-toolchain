#!/usr/bin/env python3
"""IMP-0296 probe 1: proposal / counter / concession state machine."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.protocol.negotiate import (  # noqa: E402
    IllegalTransition,
    MediatorHasNoVote,
    NegotiationSession,
    NotAParty,
    Participant,
    Role,
    Status,
)


def _parties() -> tuple[Participant, Participant]:
    return (
        Participant(id="alice", preferred=0.8, floor=0.25, ceiling=1.0),
        Participant(id="bob", preferred=0.2, floor=0.0, ceiling=0.75),
    )


def test_happy_path_ledger() -> dict:
    a, b = _parties()
    s = NegotiationSession((a, b))
    try:
        s.counter("bob", 0.2)
        raise AssertionError("counter before propose must fail")
    except IllegalTransition:
        pass
    s.propose("alice", 0.8, terms={"issue": "split", "note": "opening"})
    if s.status is not Status.OPEN:
        raise AssertionError(f"expected OPEN, got {s.status}")
    s.counter("bob", 0.2, terms={"issue": "split"})
    if s.status is not Status.ACTIVE:
        raise AssertionError(f"expected ACTIVE, got {s.status}")
    c_a = s.concede("alice", 0.65)
    c_b = s.concede("bob", 0.35)
    if not c_a.is_concession or not c_a.toward_peer:
        raise AssertionError(f"alice move should be a concession: {c_a}")
    if not c_b.is_concession or not c_b.toward_peer:
        raise AssertionError(f"bob move should be a concession: {c_b}")
    away = s.concede("alice", 0.70)
    if away.toward_peer or away.is_concession:
        raise AssertionError("move away from peer must not count as a concession")
    ledger = s.concession_ledger()
    if set(ledger) != {"alice", "bob"}:
        raise AssertionError(f"ledger parties {set(ledger)}")
    if not ledger["alice"] or not ledger["bob"]:
        raise AssertionError("each party must have a non-empty concession ledger")
    settled = s.accept("alice")
    if settled != 0.35:
        raise AssertionError(f"accept must take counterpart offer, got {settled}")
    if s.status is not Status.SETTLED:
        raise AssertionError(s.status)
    try:
        s.concede("bob", 0.4)
        raise AssertionError("concede after settle must fail")
    except IllegalTransition:
        pass
    return {"settlement": settled, "ledger_counts": {k: len(v) for k, v in ledger.items()}}


def test_reject_and_bounds() -> None:
    a, b = _parties()
    s = NegotiationSession((a, b))
    s.propose("alice", 0.8)
    s.counter("bob", 0.2)
    try:
        s.concede("alice", 0.10)
        raise AssertionError("alice below floor must fail")
    except IllegalTransition:
        pass
    s.reject("bob")
    if s.status is not Status.FAILED:
        raise AssertionError(s.status)


def test_mediator_cannot_act_as_party() -> None:
    a, b = _parties()
    med = Participant(id="med", role=Role.MEDIATOR, prior=0.9, bias=0.0)
    s = NegotiationSession((a, b), mediator=med)
    s.propose("alice", 0.8)
    s.counter("bob", 0.2)
    for fn, args in (
        (s.propose, ("med", 0.9)),
        (s.counter, ("med", 0.9)),
        (s.concede, ("med", 0.5)),
        (s.accept, ("med",)),
        (s.reject, ("med",)),
        (s.vote, ("med", 0.9)),
        (s.force_settle, ("med", 0.9)),
    ):
        try:
            fn(*args)
            raise AssertionError(f"{fn.__name__} by mediator must fail")
        except MediatorHasNoVote:
            pass
    try:
        s.vote("alice")
        raise AssertionError("party vote is not a ballot in this protocol")
    except (MediatorHasNoVote, Exception) as exc:
        if isinstance(exc, MediatorHasNoVote):
            raise AssertionError("party vote must not be classified as mediator-no-vote") from exc
    try:
        s.propose("carol", 0.5)
        raise AssertionError("unknown actor must fail")
    except NotAParty:
        pass


def test_two_party_only() -> None:
    a, b = _parties()
    extra = Participant(id="cara", preferred=0.5)
    try:
        NegotiationSession((a, b, extra))
        raise AssertionError("three parties must be refused")
    except Exception as exc:
        if "exactly two" not in str(exc):
            raise


def main() -> int:
    happy = test_happy_path_ledger()
    test_reject_and_bounds()
    test_mediator_cannot_act_as_party()
    test_two_party_only()
    payload = {
        "probe": "probe1-state-machine",
        "unit_id": "IMP-0296",
        "pass": True,
        "happy": happy,
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:IMP-0296-probe1 proposal/counter/concession state machine")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
