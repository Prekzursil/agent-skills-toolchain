"""Recusal lifecycle, quorum recomputation, recused-ballot detector (IMP-0361)."""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Any, Iterable

RECUSED_BALLOT_IN_TALLY = "RECUSED-BALLOT-IN-TALLY"


class RecusalError(Exception):
    pass


@dataclass
class Seat:
    id: str
    vendor: str = ""
    authored_artifact: bool = False
    recused: bool = False


@dataclass
class Conflict:
    kind: str
    target: str = ""
    note: str = ""


@dataclass
class Contribution:
    id: str
    seat_id: str
    kind: str
    body: str
    round_id: int = 1


@dataclass
class Ballot:
    ballot_id: str
    seat_id: str
    choice: str
    round_id: int = 1


@dataclass
class Census:
    hashes_by_id: dict[str, str] = field(default_factory=dict)
    ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"hashes_by_id": dict(self.hashes_by_id), "ids": list(self.ids)}


@dataclass
class Quorum:
    eligible_n: int
    required: int
    met: bool
    void: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible_n": self.eligible_n,
            "required": self.required,
            "met": self.met,
            "void": self.void,
        }


@dataclass
class Tally:
    counts: dict[str, int]
    decision: str | None
    counting_seat_ids: list[str]
    void_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "counts": dict(self.counts),
            "decision": self.decision,
            "counting_seat_ids": list(self.counting_seat_ids),
            "void_reason": self.void_reason,
        }


@dataclass
class TallyComparison:
    recorded: Tally
    recomputed: Tally
    differ: bool
    recused_in_recorded: bool
    recused_in_recomputed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "recorded": self.recorded.to_dict(),
            "recomputed": self.recomputed.to_dict(),
            "differ": self.differ,
            "recused_in_recorded": self.recused_in_recorded,
            "recused_in_recomputed": self.recused_in_recomputed,
        }


@dataclass
class RecusalResult:
    declared: bool
    excluded_ballot_ids: list[str]
    retained_contribution_ids: list[str]


@dataclass
class ReplaceResult:
    inherited_ballots: int
    seat_id: str


@dataclass
class Audit:
    fired: bool
    code: str | None
    leaked_seat_ids: list[str]
    leaked_ballot_ids: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "fired": self.fired,
            "code": self.code,
            "leaked_seat_ids": list(self.leaked_seat_ids),
            "leaked_ballot_ids": list(self.leaked_ballot_ids),
        }


def _hash_body(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


class RecusalSession:
    def __init__(self, seats: Iterable[Seat], quorum_ratio: float = 0.6):
        self.seats = {s.id: s for s in seats}
        self.quorum_ratio = float(quorum_ratio)
        self.initial_n = len(self.seats)
        self.contributions: list[Contribution] = []
        self.ballots: list[Ballot] = []
        self.declarations: dict[str, Conflict] = {}
        self.recused: set[str] = set()

    def add_contribution(self, item: Contribution) -> None:
        self.contributions.append(item)

    def cast_ballot(self, ballot: Ballot) -> None:
        if ballot.seat_id in self.recused:
            raise RecusalError(f"recused seat {ballot.seat_id} cannot cast")
        self.ballots.append(ballot)

    def declare(self, seat_id: str, conflict: Conflict) -> None:
        self.declarations[seat_id] = conflict

    def recuse(self, seat_id: str, reason: str = "") -> RecusalResult:
        self.recused.add(seat_id)
        if seat_id in self.seats:
            self.seats[seat_id].recused = True
        excluded = [b.ballot_id for b in self.ballots if b.seat_id == seat_id]
        retained = [c.id for c in self.contributions]
        return RecusalResult(
            declared=True,
            excluded_ballot_ids=excluded,
            retained_contribution_ids=retained,
        )

    def replace(self, old_id: str, new_seat: Seat) -> ReplaceResult:
        self.seats[new_seat.id] = new_seat
        return ReplaceResult(inherited_ballots=0, seat_id=new_seat.id)

    def replacement_ballot_count(self, seat_id: str) -> int:
        return sum(1 for b in self.ballots if b.seat_id == seat_id)

    def contribution_census(self) -> Census:
        hashes = {c.id: _hash_body(c.body) for c in self.contributions}
        return Census(hashes_by_id=hashes, ids=list(hashes))

    def census_retained(self, pre: Census, recused_id: str) -> dict[str, Any]:
        post = self.contribution_census()
        retained = all(post.hashes_by_id.get(k) == v for k, v in pre.hashes_by_id.items())
        return {"retained": retained, "pre": pre.to_dict(), "post": post.to_dict(), "recused_id": recused_id}

    def _required(self) -> int:
        return max(1, math.ceil(self.initial_n * self.quorum_ratio))

    def eligible_ids(self) -> list[str]:
        return [sid for sid, s in self.seats.items() if sid not in self.recused]

    def recompute_quorum(self) -> Quorum:
        eligible = self.eligible_ids()
        required = self._required()
        met = len(eligible) >= required
        return Quorum(eligible_n=len(eligible), required=required, met=met, void=not met)

    def recorded_ballots(self) -> list[Ballot]:
        return list(self.ballots)

    def counting_ballots(self) -> list[Ballot]:
        return [b for b in self.ballots if b.seat_id not in self.recused]

    def _tally(self, ballots: list[Ballot], counting_ids: list[str]) -> Tally:
        q = self.recompute_quorum()
        counts: dict[str, int] = {}
        for b in ballots:
            counts[b.choice] = counts.get(b.choice, 0) + 1
        if q.void:
            return Tally(counts=counts, decision=None, counting_seat_ids=counting_ids, void_reason="quorum")
        if not counts:
            return Tally(counts=counts, decision=None, counting_seat_ids=counting_ids)
        top = max(counts.values())
        winners = [k for k, v in counts.items() if v == top]
        if len(winners) != 1:
            return Tally(counts=counts, decision=None, counting_seat_ids=counting_ids)
        return Tally(counts=counts, decision=winners[0], counting_seat_ids=counting_ids)

    def recompute_tally(self) -> Tally:
        ballots = self.counting_ballots()
        return self._tally(ballots, [b.seat_id for b in ballots])

    def compare_tallies(self) -> TallyComparison:
        recorded = self._tally(self.recorded_ballots(), [b.seat_id for b in self.recorded_ballots()])
        recomputed = self.recompute_tally()
        recused_in_recorded = any(b.seat_id in self.recused for b in self.recorded_ballots())
        recused_in_recomputed = any(sid in recomputed.counting_seat_ids for sid in self.recused)
        return TallyComparison(
            recorded=recorded,
            recomputed=recomputed,
            differ=recorded.counts != recomputed.counts or recorded.decision != recomputed.decision,
            recused_in_recorded=recused_in_recorded,
            recused_in_recomputed=recused_in_recomputed,
        )

    def audit_counting_ballots(self, ballots: Iterable[Ballot]) -> Audit:
        leaked_seats = sorted({b.seat_id for b in ballots if b.seat_id in self.recused})
        leaked_ballots = [b.ballot_id for b in ballots if b.seat_id in self.recused]
        fired = bool(leaked_seats)
        return Audit(
            fired=fired,
            code=RECUSED_BALLOT_IN_TALLY if fired else "SILENT",
            leaked_seat_ids=leaked_seats,
            leaked_ballot_ids=leaked_ballots,
        )
