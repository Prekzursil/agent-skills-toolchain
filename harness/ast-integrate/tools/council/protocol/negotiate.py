"""Negotiation and mediation protocol (P12, ``adversarial-collaboration``).

Two bargaining parties hold one standing offer each on a shared numeric scale
(the probes use a 0..1 split).  A :class:`NegotiationSession` is a small state
machine over those offers::

    PENDING --propose--> OPEN --counter--> ACTIVE --accept/force_settle--> SETTLED
                                  \\            \\--reject--> FAILED
                                   \\--accept--> SETTLED / --reject--> FAILED

* ``propose`` is the opening move and may only be made once; ``counter`` puts
  the second offer on the table (or replaces a standing offer once both exist);
  ``concede`` moves a party's own standing offer and is the only move written to
  the :meth:`NegotiationSession.concession_ledger`.  A concession is scored
  against the *peer's* standing offer: the move is ``toward_peer`` when the
  distance between the two offers shrinks, and ``is_concession`` when it is
  toward the peer with non-zero magnitude.  Moving away from the peer is legal
  but is recorded as a non-concession.
* Every value a party puts on the table must lie inside that party's declared
  ``[floor, ceiling]`` band; anything else is an :class:`IllegalTransition`.
* ``accept`` closes at the *counterpart's* standing offer; ``force_settle`` closes
  at a stated value that lies inside the zone of possible agreement (the
  intersection of both bands); ``reject`` fails the bargain.  Terminal states
  refuse every further move.
* The mediator seat (``Role.MEDIATOR``) is not a party: it may :meth:`suggest`
  a settlement but every party act - propose, counter, concede, accept, reject,
  vote, force_settle - raises :class:`MediatorHasNoVote`.  There is no ballot in
  bargaining at all, so a party calling ``vote`` gets :class:`NoBallot` (an
  :class:`IllegalTransition`).  An unknown actor raises :class:`NotAParty`.

Mediator neutrality is a measurable property, not a promise.  A neutral
mediator's suggestion is exactly the midpoint of the two standing offers and
never mixes in the mediator's declared prior (``uses_prior`` is False).  A
mediator seated with ``bias`` in (0, 1] returns the convex mix
``(1 - bias) * midpoint + bias * prior`` and flags ``uses_prior``; that is the
negative control :func:`run_matched_pair_experiment` uses to show that
:func:`shift_toward_prior` fires on a captured mediator and stays at zero for a
neutral one over matched runs.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable

__all__ = [
    "PROTOCOL_ID",
    "NegotiationError",
    "IllegalTransition",
    "NoBallot",
    "NotAParty",
    "MediatorHasNoVote",
    "Role",
    "Status",
    "Participant",
    "Move",
    "Suggestion",
    "NegotiationSession",
    "simulate_negotiation",
    "shift_toward_prior",
    "matched_openings",
    "run_matched_pair_experiment",
]

PROTOCOL_ID = "P12"

# --------------------------------------------------------------------------- errors


class NegotiationError(Exception):
    """Base class for every protocol violation raised by this module."""


class IllegalTransition(NegotiationError):
    """The move is not legal in the session's current state (or value band)."""


class NoBallot(IllegalTransition):
    """Bargaining has no ballot: parties settle by accept/counter/concede."""


class NotAParty(NegotiationError, KeyError):
    """The actor is neither a seated party nor the mediator."""

    def __str__(self) -> str:  # KeyError quotes its argument; keep the message readable
        return NegotiationError.__str__(self)


class MediatorHasNoVote(NegotiationError):
    """The mediator suggests; it may not propose, counter, concede, accept, reject or vote."""


# --------------------------------------------------------------------------- enums / records


class Role(Enum):
    """Seat kind in a negotiation."""

    PARTY = "party"
    MEDIATOR = "mediator"


class Status(Enum):
    """Session state.  ``SETTLED`` and ``FAILED`` are terminal."""

    PENDING = "pending"
    OPEN = "open"
    ACTIVE = "active"
    SETTLED = "settled"
    FAILED = "failed"

    @property
    def terminal(self) -> bool:
        return self in (Status.SETTLED, Status.FAILED)


def _finite(value: Any, what: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{what} must be a number, got {value!r}") from exc
    if math.isnan(number) or math.isinf(number):
        raise ValueError(f"{what} must be finite, got {value!r}")
    return number


@dataclass(frozen=True)
class Participant:
    """A seat: a bargaining party (default) or the mediator.

    ``preferred`` is the party's ideal point (optional; used as the opening offer
    by :func:`simulate_negotiation`); ``floor``/``ceiling`` bound every value the
    party may put on the table.  ``prior`` and ``bias`` are read only for a
    mediator: ``prior`` is the settlement the mediator privately favours and
    ``bias`` in [0, 1] is how much of it leaks into suggestions (0 = neutral).
    """

    id: str
    preferred: float | None = None
    floor: float = 0.0
    ceiling: float = 1.0
    role: Role = Role.PARTY
    prior: float | None = None
    bias: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("participant id must be a non-empty string")
        if not isinstance(self.role, Role):
            raise ValueError(f"{self.id}: role must be a Role, got {self.role!r}")
        floor = _finite(self.floor, f"{self.id}.floor")
        ceiling = _finite(self.ceiling, f"{self.id}.ceiling")
        if floor > ceiling:
            raise ValueError(f"{self.id}: floor {floor} exceeds ceiling {ceiling}")
        if self.preferred is not None:
            preferred = _finite(self.preferred, f"{self.id}.preferred")
            if not floor <= preferred <= ceiling:
                raise ValueError(
                    f"{self.id}: preferred {preferred} outside band [{floor}, {ceiling}]"
                )
        bias = _finite(self.bias, f"{self.id}.bias")
        if not 0.0 <= bias <= 1.0:
            raise ValueError(f"{self.id}: bias must lie in [0, 1], got {bias}")
        if self.prior is not None:
            _finite(self.prior, f"{self.id}.prior")
        if self.role is Role.MEDIATOR and bias > 0.0 and self.prior is None:
            raise ValueError(f"{self.id}: a biased mediator must declare the prior it leans to")

    @property
    def is_mediator(self) -> bool:
        return self.role is Role.MEDIATOR

    def in_band(self, value: float) -> bool:
        return self.floor <= value <= self.ceiling


@dataclass(frozen=True)
class Move:
    """One recorded act.  ``as_dict`` is the ledger row shape."""

    kind: str
    party: str
    from_value: float | None
    to_value: float | None
    magnitude: float
    toward_peer: bool
    is_concession: bool
    terms: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        row: dict[str, Any] = {
            "kind": self.kind,
            "party": self.party,
            "from": self.from_value,
            "from_value": self.from_value,
            "to": self.to_value,
            "to_value": self.to_value,
            "magnitude": self.magnitude,
            "toward_peer": self.toward_peer,
            "is_concession": self.is_concession,
        }
        if self.terms:
            row["terms"] = dict(self.terms)
        return row


@dataclass(frozen=True)
class Suggestion:
    """A mediator's proposed settlement and exactly how it was formed."""

    value: float
    midpoint: float
    offers: dict[str, float]
    prior: float | None
    bias: float
    uses_prior: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "midpoint": self.midpoint,
            "offers": dict(self.offers),
            "prior": self.prior,
            "bias": self.bias,
            "uses_prior": self.uses_prior,
        }


# --------------------------------------------------------------------------- session


class NegotiationSession:
    """Two-party bargaining with an optional non-voting mediator."""

    def __init__(
        self,
        parties: Iterable[Participant],
        mediator: Participant | None = None,
    ) -> None:
        seats = tuple(parties)
        if len(seats) != 2:
            raise ValueError(
                f"a negotiation has exactly two bargaining parties, got {len(seats)}"
            )
        for seat in seats:
            if not isinstance(seat, Participant):
                raise TypeError(f"parties must be Participant instances, got {seat!r}")
            if seat.is_mediator:
                raise ValueError(f"{seat.id}: a mediator cannot be seated as a bargaining party")
        if seats[0].id == seats[1].id:
            raise ValueError(f"both parties are named {seats[0].id!r}")
        if mediator is not None:
            if not isinstance(mediator, Participant):
                raise TypeError(f"mediator must be a Participant, got {mediator!r}")
            if not mediator.is_mediator:
                raise ValueError(f"{mediator.id}: mediator seat must carry Role.MEDIATOR")
            if mediator.id in (seats[0].id, seats[1].id):
                raise ValueError(f"{mediator.id}: mediator id collides with a party")
        self._parties: dict[str, Participant] = {seat.id: seat for seat in seats}
        self._mediator = mediator
        self._offers: dict[str, float | None] = {seat.id: None for seat in seats}
        self._terms: dict[str, dict[str, Any]] = {seat.id: {} for seat in seats}
        self._ledger: dict[str, list[Move]] = {seat.id: [] for seat in seats}
        self._moves: list[Move] = []
        self._suggestions: list[Suggestion] = []
        self._status = Status.PENDING
        self._settlement: float | None = None

    # ---- read side -------------------------------------------------------------

    @property
    def status(self) -> Status:
        return self._status

    @property
    def parties(self) -> tuple[str, str]:
        ids = tuple(self._parties)
        return ids[0], ids[1]

    @property
    def mediator(self) -> Participant | None:
        return self._mediator

    @property
    def offers(self) -> dict[str, float | None]:
        return dict(self._offers)

    @property
    def settlement(self) -> float | None:
        return self._settlement

    @property
    def moves(self) -> tuple[Move, ...]:
        return tuple(self._moves)

    @property
    def suggestions(self) -> tuple[Suggestion, ...]:
        return tuple(self._suggestions)

    def participant(self, actor: str) -> Participant:
        """The seated participant named ``actor`` (party or mediator)."""
        if self._mediator is not None and actor == self._mediator.id:
            return self._mediator
        try:
            return self._parties[actor]
        except KeyError:
            raise NotAParty(f"{actor!r} is not a party to this negotiation") from None

    def peer_of(self, actor: str) -> Participant:
        """The other bargaining party."""
        party = self._party(actor, "act")
        for seat in self._parties.values():
            if seat.id != party.id:
                return seat
        raise NotAParty(actor)  # unreachable: two distinct parties are enforced

    def zone_of_possible_agreement(self) -> tuple[float, float] | None:
        """Intersection of both parties' bands, or None when the bands are disjoint."""
        first, second = self._parties.values()
        low = max(first.floor, second.floor)
        high = min(first.ceiling, second.ceiling)
        if low > high:
            return None
        return low, high

    def concession_ledger(self) -> dict[str, list[dict[str, Any]]]:
        """Per-party list of every ``concede`` move (concessions and non-concessions)."""
        return {pid: [move.as_dict() for move in rows] for pid, rows in self._ledger.items()}

    def transcript(self) -> list[dict[str, Any]]:
        """Every recorded move in order."""
        return [move.as_dict() for move in self._moves]

    def as_dict(self) -> dict[str, Any]:
        return {
            "protocol": PROTOCOL_ID,
            "status": self._status.value,
            "parties": list(self._parties),
            "mediator": None if self._mediator is None else self._mediator.id,
            "offers": self.offers,
            "settlement": self._settlement,
            "zone_of_possible_agreement": self.zone_of_possible_agreement(),
            "moves": self.transcript(),
            "concession_ledger": self.concession_ledger(),
            "suggestions": [s.as_dict() for s in self._suggestions],
        }

    # ---- guards ----------------------------------------------------------------

    def _party(self, actor: str, action: str) -> Participant:
        if self._mediator is not None and actor == self._mediator.id:
            raise MediatorHasNoVote(
                f"mediator {actor!r} may not {action}: the mediator suggests, it has no vote"
            )
        try:
            return self._parties[actor]
        except KeyError:
            raise NotAParty(f"{actor!r} is not a party to this negotiation") from None

    def _require(self, action: str, *allowed: Status) -> None:
        if self._status not in allowed:
            names = "/".join(s.value for s in allowed)
            raise IllegalTransition(
                f"cannot {action} while {self._status.value}; legal only when {names}"
            )

    def _banded(self, party: Participant, value: Any, action: str) -> float:
        try:
            number = _finite(value, f"{party.id} {action} value")
        except ValueError as exc:
            raise IllegalTransition(str(exc)) from None
        if not party.in_band(number):
            raise IllegalTransition(
                f"{party.id} cannot {action} {number}: outside the acceptable band "
                f"[{party.floor}, {party.ceiling}]"
            )
        return number

    def _record(self, move: Move) -> Move:
        self._moves.append(move)
        return move

    # ---- party moves -------------------------------------------------------------

    def propose(self, actor: str, value: float, terms: dict[str, Any] | None = None) -> Move:
        """Opening offer.  Legal once, from PENDING; moves the session to OPEN."""
        party = self._party(actor, "propose")
        self._require("propose", Status.PENDING)
        number = self._banded(party, value, "propose")
        self._offers[party.id] = number
        self._terms[party.id] = dict(terms or {})
        self._status = Status.OPEN
        return self._record(
            Move("propose", party.id, None, number, 0.0, False, False, dict(terms or {}))
        )

    def counter(self, actor: str, value: float, terms: dict[str, Any] | None = None) -> Move:
        """Put a competing offer on the table (OPEN -> ACTIVE) or replace one (ACTIVE)."""
        party = self._party(actor, "counter")
        self._require("counter", Status.OPEN, Status.ACTIVE)
        if self._status is Status.OPEN and self._offers[party.id] is not None:
            raise IllegalTransition(
                f"{party.id} already holds the only offer; the counter must come from "
                f"{self.peer_of(party.id).id}"
            )
        number = self._banded(party, value, "counter")
        previous = self._offers[party.id]
        self._offers[party.id] = number
        self._terms[party.id] = dict(terms or {})
        self._status = Status.ACTIVE
        magnitude = 0.0 if previous is None else abs(number - previous)
        return self._record(
            Move("counter", party.id, previous, number, magnitude, False, False, dict(terms or {}))
        )

    def concede(self, actor: str, value: float) -> Move:
        """Move one's own standing offer; scored against the peer's offer and ledgered."""
        party = self._party(actor, "concede")
        self._require("concede", Status.ACTIVE)
        number = self._banded(party, value, "concede to")
        previous = self._offers[party.id]
        peer_offer = self._offers[self.peer_of(party.id).id]
        if previous is None or peer_offer is None:
            raise IllegalTransition(f"{party.id} has nothing to concede from")
        before = abs(previous - peer_offer)
        after = abs(number - peer_offer)
        magnitude = abs(number - previous)
        toward_peer = after < before
        move = Move(
            "concede", party.id, previous, number, magnitude, toward_peer, toward_peer and magnitude > 0.0
        )
        self._offers[party.id] = number
        self._ledger[party.id].append(move)
        return self._record(move)

    def accept(self, actor: str) -> float:
        """Close at the counterpart's standing offer; returns the settlement."""
        party = self._party(actor, "accept")
        self._require("accept", Status.OPEN, Status.ACTIVE)
        peer = self.peer_of(party.id)
        peer_offer = self._offers[peer.id]
        if peer_offer is None:
            raise IllegalTransition(f"{party.id} cannot accept: {peer.id} has made no offer")
        self._settlement = peer_offer
        self._status = Status.SETTLED
        self._record(Move("accept", party.id, self._offers[party.id], peer_offer, 0.0, False, False))
        return peer_offer

    def reject(self, actor: str) -> None:
        """Walk away; the bargain FAILS."""
        party = self._party(actor, "reject")
        self._require("reject", Status.OPEN, Status.ACTIVE)
        self._status = Status.FAILED
        self._record(Move("reject", party.id, self._offers[party.id], None, 0.0, False, False))

    def vote(self, actor: str, value: float | None = None) -> None:
        """There is no ballot in bargaining.  Mediator -> MediatorHasNoVote; party -> NoBallot."""
        party = self._party(actor, "vote")
        raise NoBallot(
            f"{party.id} cannot vote: this protocol has no ballot; parties settle by "
            "accept(), counter() or concede()"
        )

    def force_settle(self, actor: str, value: float) -> float:
        """Close at ``value`` when it lies in the zone of possible agreement (both bands)."""
        party = self._party(actor, "force a settlement")
        self._require("force_settle", Status.ACTIVE)
        try:
            number = _finite(value, f"{party.id} force_settle value")
        except ValueError as exc:
            raise IllegalTransition(str(exc)) from None
        zone = self.zone_of_possible_agreement()
        if zone is None:
            raise IllegalTransition("no zone of possible agreement: the parties' bands are disjoint")
        if not zone[0] <= number <= zone[1]:
            raise IllegalTransition(
                f"{party.id} cannot force {number}: outside the zone of possible agreement "
                f"[{zone[0]}, {zone[1]}]"
            )
        self._settlement = number
        self._status = Status.SETTLED
        self._record(Move("force_settle", party.id, self._offers[party.id], number, 0.0, False, False))
        return number

    # ---- mediator ----------------------------------------------------------------

    def suggest(self) -> Suggestion:
        """The mediator's proposed settlement, formed from the two standing offers.

        Neutral (``bias == 0``): exactly the midpoint, ``uses_prior`` False.
        Biased: ``(1 - bias) * midpoint + bias * prior`` and ``uses_prior`` True.
        """
        if self._mediator is None:
            raise IllegalTransition("no mediator is seated in this negotiation")
        self._require("suggest", Status.ACTIVE)
        first, second = self.parties
        first_offer, second_offer = self._offers[first], self._offers[second]
        if first_offer is None or second_offer is None:
            raise IllegalTransition("both offers must be on the table before a suggestion")
        midpoint = (first_offer + second_offer) / 2.0
        bias = float(self._mediator.bias)
        prior = self._mediator.prior
        if bias > 0.0 and prior is not None:
            value = (1.0 - bias) * midpoint + bias * float(prior)
            uses_prior = True
        else:
            value = midpoint
            uses_prior = False
        suggestion = Suggestion(
            value=value,
            midpoint=midpoint,
            offers={first: first_offer, second: second_offer},
            prior=None if prior is None else float(prior),
            bias=bias,
            uses_prior=uses_prior,
        )
        self._suggestions.append(suggestion)
        return suggestion

    def adopt(self, suggestion: Suggestion | None = None) -> float:
        """Both parties concede to a suggestion and the first party accepts it.

        Uses the latest suggestion when none is given.  Each concession is
        band-checked like any other, so a suggestion outside a party's band is
        an :class:`IllegalTransition` rather than a silent settlement.
        """
        if suggestion is None:
            if not self._suggestions:
                raise IllegalTransition("no suggestion to adopt")
            suggestion = self._suggestions[-1]
        first, second = self.parties
        for pid in (first, second):
            if self._offers[pid] != suggestion.value:
                self.concede(pid, suggestion.value)
        return self.accept(first)


# --------------------------------------------------------------------------- experiments


def simulate_negotiation(
    alice_open: float,
    bob_open: float,
    mediator: Participant | None = None,
    *,
    alice: Participant | None = None,
    bob: Participant | None = None,
) -> dict[str, Any]:
    """Run one bargain to settlement and return its outcome.

    Without a mediator the parties split the difference: each concedes to the
    midpoint of the two openings and the proposer accepts.  With a mediator the
    parties adopt the mediator's :meth:`NegotiationSession.suggest`.  The result
    records the settlement, whether the mediator's prior entered it, the
    suggestion, and the concession ledger.
    """
    party_a = alice or Participant(id="alice", preferred=alice_open)
    party_b = bob or Participant(id="bob", preferred=bob_open)
    session = NegotiationSession((party_a, party_b), mediator=mediator)
    session.propose(party_a.id, alice_open)
    session.counter(party_b.id, bob_open)
    suggestion: Suggestion | None = None
    if mediator is not None:
        suggestion = session.suggest()
        session.adopt(suggestion)
    else:
        midpoint = (alice_open + bob_open) / 2.0
        session.concede(party_a.id, midpoint)
        session.concede(party_b.id, midpoint)
        session.accept(party_a.id)
    return {
        "opening": {party_a.id: alice_open, party_b.id: bob_open},
        "mediator": None if mediator is None else mediator.id,
        "settlement": session.settlement,
        "status": session.status.value,
        "used_prior": bool(suggestion.uses_prior) if suggestion is not None else False,
        "suggestion": None if suggestion is None else suggestion.as_dict(),
        "ledger": session.concession_ledger(),
    }


def shift_toward_prior(prior: float, baseline: float, outcome: float) -> float:
    """Signed displacement of ``outcome`` from ``baseline`` along the direction of ``prior``.

    Positive means the outcome moved toward the prior, negative away from it,
    zero when the outcome equals the baseline.  Unnormalised: the unit is the
    offer scale, so ``0.2475`` is a quarter of the scale.
    """
    direction = 1.0 if prior >= baseline else -1.0
    return direction * (outcome - baseline)


def matched_openings(n: int) -> list[tuple[float, float]]:
    """``n`` symmetric opening pairs around 0.5: alice ``0.80 + 0.01*k``, bob ``0.20 - 0.01*k``.

    ``k`` cycles through 0..14 so every opening stays inside the default band.
    """
    if int(n) < 1:
        raise ValueError(f"n must be >= 1, got {n}")
    pairs = []
    for i in range(int(n)):
        k = i % 15
        pairs.append((round(0.80 + 0.01 * k, 4), round(0.20 - 0.01 * k, 4)))
    return pairs


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def run_matched_pair_experiment(
    n: int = 10,
    *,
    prior: float = 0.95,
    bias: float = 0.55,
) -> dict[str, Any]:
    """Three arms per matched opening: no mediator, neutral mediator, biased mediator.

    For each of ``n`` opening pairs the same bargain runs without a mediator
    (baseline), with a neutral mediator (``bias=0``, prior declared) and with a
    biased mediator (``bias`` toward ``prior``, the negative control).  The
    :func:`shift_toward_prior` of each mediated settlement against the baseline
    is recorded per pair and averaged; a neutral mediator must produce a mean
    shift of zero and never use its prior, the biased one must move every run.
    """
    if not 0.0 < float(bias) <= 1.0:
        raise ValueError(f"bias for the negative control must lie in (0, 1], got {bias}")
    prior = _finite(prior, "prior")
    neutral_med = Participant(id="med", role=Role.MEDIATOR, prior=prior, bias=0.0)
    biased_med = Participant(id="med", role=Role.MEDIATOR, prior=prior, bias=float(bias))
    pairs: list[dict[str, Any]] = []
    ledger_parties: set[str] = set()
    for i, (a_open, b_open) in enumerate(matched_openings(n)):
        without = simulate_negotiation(a_open, b_open)
        neutral = simulate_negotiation(a_open, b_open, mediator=neutral_med)
        biased = simulate_negotiation(a_open, b_open, mediator=biased_med)
        for run in (without, neutral, biased):
            ledger_parties.update(run["ledger"])
        pairs.append(
            {
                "i": i,
                "opening": {"alice": a_open, "bob": b_open},
                "without": without["settlement"],
                "neutral": neutral["settlement"],
                "biased": biased["settlement"],
                "neutral_shift_toward_prior": shift_toward_prior(
                    prior, without["settlement"], neutral["settlement"]
                ),
                "biased_shift_toward_prior": shift_toward_prior(
                    prior, without["settlement"], biased["settlement"]
                ),
                "neutral_used_prior": neutral["used_prior"],
                "biased_used_prior": biased["used_prior"],
            }
        )
    return {
        "n": len(pairs),
        "prior": prior,
        "bias": float(bias),
        "ledger_parties": sorted(ledger_parties),
        "mean_without": _mean([p["without"] for p in pairs]),
        "mean_neutral": _mean([p["neutral"] for p in pairs]),
        "mean_biased": _mean([p["biased"] for p in pairs]),
        "mean_neutral_shift_toward_prior": _mean([p["neutral_shift_toward_prior"] for p in pairs]),
        "mean_biased_shift_toward_prior": _mean([p["biased_shift_toward_prior"] for p in pairs]),
        "any_neutral_used_prior": any(p["neutral_used_prior"] for p in pairs),
        "all_biased_used_prior": all(p["biased_used_prior"] for p in pairs),
        "pairs": pairs,
    }
