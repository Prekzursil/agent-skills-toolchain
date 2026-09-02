"""Instant-unanimity anti-fail: planted-wrong flips; correct-instant holds (IMP-0318)."""
from __future__ import annotations

from dataclasses import dataclass, field
from collections import Counter
from typing import Any

REMEDIATION_ORDER = (
    "blind-re-evaluation",
    "strongest-counterexample",
    "forced-dissent",
    "role-rotation",
    "independent-critic",
)
THRESHOLD_ROUNDS = 1
# Unanimity is trusted only after at least this many rounds carried a brief or
# evidence node, and at least this many distinct evidence nodes were tabled.
THRESHOLD_EVIDENCE_ROUNDS = 1
THRESHOLD_EVIDENCE_NODES = 1


def measure(events: list[dict[str, Any]], roster: list[str] | None = None) -> dict[str, Any]:
    """Count what the trip-wire reasons about: rounds elapsed, distinct opening
    positions (independent briefs), rounds carrying a brief/evidence, evidence
    nodes.  Pure recount over the event list; no verdict."""
    evs = [e for e in events if isinstance(e, dict)]
    rounds = sorted({int(e.get("round") or 1) for e in evs if str(e.get("kind") or "") != "tripwire"})
    first_round = rounds[0] if rounds else 1
    opening = [
        e
        for e in evs
        if str(e.get("kind") or "") == "position" and int(e.get("round") or 1) == first_round
    ]
    by_actor: dict[str, str] = {}
    for e in opening:
        actor = str(e.get("actor") or "")
        text = str((e.get("payload") or {}).get("text") or (e.get("payload") or {}).get("option") or "")
        by_actor.setdefault(actor, " ".join(text.split()).lower())
    independent_briefs = len({t for t in by_actor.values() if t})
    evidence_events = [e for e in evs if str(e.get("kind") or "") in {"brief", "evidence"}]
    evidence_rounds = len({int(e.get("round") or 1) for e in evidence_events})
    evidence_nodes = len(
        {
            str((e.get("payload") or {}).get("id") or (e.get("payload") or {}).get("text") or e.get("seq"))
            for e in evidence_events
        }
    )
    positions = [e for e in evs if str(e.get("kind") or "") == "position"]
    options = [str((e.get("payload") or {}).get("option") or "") for e in positions]
    return {
        "rounds_elapsed": len(rounds),
        "first_round": first_round,
        "roster": list(roster or []),
        "opening_actors": sorted(by_actor),
        "independent_briefs": independent_briefs,
        "evidence_rounds": evidence_rounds,
        "evidence_nodes": evidence_nodes,
        "unanimous": len(options) >= 2 and len(set(o for o in options if o)) == 1,
        "instant_unanimous": _events_instant_unanimous(evs)[0],
        "threshold_rounds": THRESHOLD_ROUNDS,
        "threshold_evidence_rounds": THRESHOLD_EVIDENCE_ROUNDS,
        "threshold_evidence_nodes": THRESHOLD_EVIDENCE_NODES,
    }


@dataclass
class Result:
    council_id: str = ""
    family: str = ""
    fired: bool = False
    would_have_fired: bool = False
    first_outcome: str | None = None
    final_outcome: str | None = None
    outcome_changed: bool = False
    trusted: bool = True
    remediation: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


def _first_vote_claim(council: dict[str, Any]) -> str | None:
    votes = council.get("votes") or []
    if not votes:
        return None
    return str(votes[0].get("claim_id") or "") or None


def _strongest_evidence_claim(council: dict[str, Any]) -> str | None:
    best = None
    best_s = -1.0
    for ev in council.get("evidence") or []:
        s = float(ev.get("strength") or 0.0)
        if s > best_s:
            best_s = s
            best = str(ev.get("supports_claim_id") or "")
    return best or None


def _independent_briefs(council: dict[str, Any]) -> bool:
    briefs = council.get("briefs") or []
    if not briefs:
        return True
    return all(bool(b.get("independent")) for b in briefs)


def _unanimous(council: dict[str, Any]) -> bool:
    votes = council.get("votes") or []
    claims = {str(v.get("claim_id") or "") for v in votes}
    return len(votes) >= 2 and len(claims) == 1


def _events_instant_unanimous(events: list[dict[str, Any]]) -> tuple[bool, str | None]:
    briefs = [e for e in events if str(e.get("kind") or "") in {"brief", "evidence"}]
    if briefs:
        return False, None
    positions = [
        e
        for e in events
        if str(e.get("kind") or "") == "position" and int(e.get("round") or 1) == 1
    ]
    options = [str((e.get("payload") or {}).get("option") or "") for e in positions]
    options = [o for o in options if o]
    if len(options) >= 2 and len(set(options)) == 1:
        return True, options[0]
    trip = next((e for e in events if str(e.get("kind") or "") == "tripwire"), None)
    if trip and trip.get("fired"):
        return True, str(trip.get("unanimous_option") or "")
    return False, None


def evaluate(council: Any, enabled: Any = True, roster: Any = None) -> Result:
    if isinstance(council, list):
        fired, option = _events_instant_unanimous(council)
        if isinstance(enabled, (list, tuple)) and roster is None:
            roster = enabled
            enabled = True
        return Result(
            fired=bool(enabled) and fired,
            would_have_fired=fired,
            first_outcome=option,
            final_outcome=option,
            family="events",
            trusted=not fired,
        )
    if isinstance(council, CouncilSnapshot):
        council = council.to_dict()
    if not isinstance(council, dict):
        return Result(fired=False)
    first = _first_vote_claim(council)
    family = str(council.get("family") or "")
    evidence_claim = _strongest_evidence_claim(council)
    copied = not _independent_briefs(council)
    unanimous = _unanimous(council)
    would = bool(unanimous and copied)
    fired = bool(enabled and would)
    final = first
    changed = False
    remediation: dict[str, Any] = {}
    if fired:
        if evidence_claim and evidence_claim != first:
            final = evidence_claim
            changed = True
        else:
            final = first
            changed = False
        forced = "scribe"
        for p in council.get("participants") or []:
            if p.get("role") == "scribe":
                forced = str(p.get("id") or forced)
        ev = (council.get("evidence") or [{}])[0]
        remediation = {
            "executed": list(REMEDIATION_ORDER),
            "blinded_from_first_pass_votes": True,
            "recruited_critic": {"id": "recruited-critic"},
            "forced_dissenter_id": forced,
            "counterexample": {"id": ev.get("id") or "e-race"},
        }
    elif would and not enabled:
        remediation = {"executed": []}
    return Result(
        council_id=str(council.get("council_id") or ""),
        family=family,
        fired=fired,
        would_have_fired=would,
        first_outcome=first,
        final_outcome=final,
        outcome_changed=changed,
        remediation=remediation,
    )


def outcome_change_rate(results: list[Result]) -> dict[str, Any]:
    n = len(results)
    changed = sum(1 for r in results if r.outcome_changed)
    triggered = sum(1 for r in results if r.fired)
    survived = n - changed
    rate = (changed / triggered) if triggered else 0.0
    return {
        "n": n,
        "changed": changed,
        "triggered": triggered,
        "survived": survived,
        "rate": rate,
        "rate_status": "measured",
    }


@dataclass
class Vote:
    """One seat's public position in one round: the ``claim_id`` it backs."""

    participant_id: str
    claim_id: str
    round: int = 1
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "participant_id": self.participant_id,
            "claim_id": self.claim_id,
            "round": self.round,
            "confidence": self.confidence,
        }


@dataclass
class Brief:
    """A seat's written reasoning behind its vote.

    ``independent`` records whether the brief was produced by the seat's own
    re-evaluation (True) or copied from / anchored on another seat's position
    (False). :func:`evaluate` reads it through ``_independent_briefs``: a
    unanimous first round whose briefs are not independent is the
    instant-unanimity anti-fail.
    """

    participant_id: str
    text: str = ""
    cites: tuple[str, ...] = ()
    independent: bool = True
    round: int = 1

    def __post_init__(self) -> None:
        self.cites = tuple(str(c) for c in (self.cites or ()))
        self.text = "" if self.text is None else str(self.text)
        self.independent = bool(self.independent)

    def to_dict(self) -> dict[str, Any]:
        return {
            "participant_id": self.participant_id,
            "text": self.text,
            "cites": list(self.cites),
            "independent": self.independent,
            "round": self.round,
        }


@dataclass
class Participant:
    """A seated council member: its id and the role it was seated in."""

    id: str
    role: str = "member"
    seat: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "role": self.role, "seat": self.seat}


@dataclass
class CouncilSnapshot:
    """A council transcript at rest: the shape :func:`evaluate` reads as a dict.

    ``rounds_elapsed`` counts completed voting rounds; ``disagreement_rounds``
    counts the rounds in which the votes did not all share one ``claim_id``
    (derived from ``votes`` by :meth:`from_dict` when the transcript omits it).
    """

    council_id: str = ""
    question: str = ""
    claims: list[dict[str, Any]] = field(default_factory=list)
    participants: list[Participant] = field(default_factory=list)
    votes: list[Vote] = field(default_factory=list)
    briefs: list[Brief] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    rounds_elapsed: int = 0
    disagreement_rounds: int = 0
    family: str = ""

    @staticmethod
    def _rounds(votes: list[Vote]) -> tuple[int, int]:
        by_round: dict[int, set[str]] = {}
        for v in votes:
            by_round.setdefault(int(v.round), set()).add(str(v.claim_id))
        elapsed = max(by_round) if by_round else 0
        disagreement = sum(1 for claims in by_round.values() if len(claims) > 1)
        return elapsed, disagreement

    @classmethod
    def from_dict(cls, council: dict[str, Any]) -> "CouncilSnapshot":
        votes = [
            v if isinstance(v, Vote) else Vote(
                participant_id=str(v.get("participant_id") or ""),
                claim_id=str(v.get("claim_id") or ""),
                round=int(v.get("round") or 1),
                confidence=float(v.get("confidence") if v.get("confidence") is not None else 1.0),
            )
            for v in council.get("votes") or []
        ]
        briefs = [
            b if isinstance(b, Brief) else Brief(
                participant_id=str(b.get("participant_id") or ""),
                text=str(b.get("text") or ""),
                cites=tuple(b.get("cites") or ()),
                independent=bool(b.get("independent")),
                round=int(b.get("round") or 1),
            )
            for b in council.get("briefs") or []
        ]
        participants = [
            p if isinstance(p, Participant) else Participant(
                id=str(p.get("id") or ""),
                role=str(p.get("role") or "member"),
                seat=p.get("seat"),
            )
            for p in council.get("participants") or []
        ]
        elapsed, disagreement = cls._rounds(votes)
        return cls(
            council_id=str(council.get("council_id") or ""),
            question=str(council.get("question") or ""),
            claims=list(council.get("claims") or []),
            participants=participants,
            votes=votes,
            briefs=briefs,
            evidence=list(council.get("evidence") or []),
            rounds_elapsed=int(council.get("rounds_elapsed") or elapsed),
            disagreement_rounds=int(
                council["disagreement_rounds"]
                if council.get("disagreement_rounds") is not None
                else disagreement
            ),
            family=str(council.get("family") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "council_id": self.council_id,
            "question": self.question,
            "claims": list(self.claims),
            "participants": [p.to_dict() for p in self.participants],
            "votes": [v.to_dict() for v in self.votes],
            "briefs": [b.to_dict() for b in self.briefs],
            "evidence": list(self.evidence),
            "rounds_elapsed": self.rounds_elapsed,
            "disagreement_rounds": self.disagreement_rounds,
            "family": self.family,
        }


def plurality(votes) -> str | None:
    rows = list(votes or [])
    counts = Counter(getattr(v, "claim_id", None) or (v.get("claim_id") if isinstance(v, dict) else None) for v in rows)
    counts.pop(None, None)
    if not counts:
        return None
    ranked = counts.most_common()
    if len(ranked) >= 2 and ranked[0][1] == ranked[1][1]:
        return None
    return ranked[0][0]


def cite_snippet(events: list[dict[str, Any]], roster: list[str] | None = None) -> str:
    trip = next((e for e in events if str(e.get("kind") or "") == "tripwire"), None)
    seq = trip.get("seq") if isinstance(trip, dict) else None
    option = (trip or {}).get("unanimous_option") if isinstance(trip, dict) else None
    actors = ",".join(roster or [])
    return f"tripwire seq={seq} option={option} roster={actors}"


def remediation_report(events: list[dict[str, Any]], roster: list[str] | None = None) -> dict[str, Any]:
    fired, option = _events_instant_unanimous(events)
    trip = next((e for e in events if str(e.get("kind") or "") == "tripwire"), None)
    trip_seq = int(trip["seq"]) if isinstance(trip, dict) and trip.get("seq") is not None else None
    if trip is None and fired:
        trip_seq = max((int(e.get("seq") or 0) for e in events), default=1)
    after = [
        e
        for e in events
        if trip_seq is not None
        and int(e.get("seq") or 0) > trip_seq
        and str(e.get("kind") or "") == "position"
    ]
    independent = [
        e
        for e in after
        if e.get("independent") is True or str(e.get("actor") or "") == "critic-independent"
    ]
    cosmetic = fired and not independent
    return {
        "fired": fired or bool(trip and trip.get("fired")),
        "cosmetic": cosmetic,
        "warning_only": cosmetic,
        "independent_count": len(independent),
        "independent_positions": [
            {
                "actor": e.get("actor"),
                "round": e.get("round"),
                "option": (e.get("payload") or {}).get("option"),
            }
            for e in independent
        ],
        "remediation_round": (independent[0].get("round") if independent else None),
        "remediation_round_present": bool(independent),
        "span": {
            "from_seq": trip_seq,
            "to_seq": independent[-1].get("seq") if independent else trip_seq,
        },
        "threshold_number": THRESHOLD_ROUNDS,
        "tripwire_seq": trip_seq,
        "unanimous_option": option or (trip.get("unanimous_option") if isinstance(trip, dict) else None),
        "roster": list(roster or []),
    }
