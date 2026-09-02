#!/usr/bin/env python3
"""Typed council SDK: build a CouncilSpec, execute it deterministically, inspect it.

Two units import this module and their probes are its contract:

* IMP-0326 -- typed results and SDK/CLI artifact-key parity. :class:`CouncilSDK`
  (``build_fixture`` / ``execute`` / ``inspect`` / ``persist`` / ``load``),
  :func:`assert_typed_result`, :func:`sdk_reachable_keys`, :func:`surface_parity`
  and the ``inspect --run-dir`` CLI at the bottom of this file.
* ADV-0103 -- the council as a deterministic stance runner in which the judge is
  one seat among many. :class:`CouncilSpecBuilder` (``spec_id`` / ``question`` /
  ``charter`` / ``add_participant`` / ``stopping``), :func:`execute_spec`, the
  module-level majority rule :func:`_decide`, ``CouncilResult.artifact_map()``
  and :func:`jsonable`.

Engine model. A spec names participants (id, role, stance) and a stopping rule.
In every round each participant contributes one transcript turn and casts one
ballot derived from its stance (support -> for, oppose -> against, neutral ->
abstain). The tally of the last completed round is decided by an unweighted
majority: no role is weighted and no seat can override the count. Transcript
turns and ballots are appended per seat *before* the decision is derived, so
they remain an independent recovery path when any single seat is wrong.

Every value in a :class:`CouncilResult` is a dataclass or an enum. The result
carries no timestamps and no absolute paths, so two runs of the same spec and
run id serialise byte-for-byte identically through :func:`jsonable`.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterator, Mapping

__all__ = [
    "ARTIFACT_KEYS",
    "ENGINE_NAME",
    "ENGINE_VERSION",
    "RESULT_FILENAME",
    "STANCE_VOTES",
    "STOPPING_KINDS",
    "Ballot",
    "Budgets",
    "CouncilResult",
    "CouncilSDK",
    "CouncilSpec",
    "CouncilSpecBuilder",
    "CouncilSpecError",
    "Decision",
    "DecisionStatus",
    "Event",
    "EventLog",
    "Integrity",
    "Meta",
    "Outcome",
    "Parity",
    "Participant",
    "Plan",
    "RoundPlan",
    "Stopping",
    "StoppingRule",
    "Transcript",
    "Turn",
    "VoteTally",
    "VoteValue",
    "Votes",
    "assert_typed_result",
    "cli_inspect_payload",
    "execute_spec",
    "jsonable",
    "sdk_reachable_keys",
    "surface_parity",
    "validate_spec",
]

ENGINE_NAME = "local-deterministic"
ENGINE_VERSION = "1"
RESULT_FILENAME = "council-result.json"

#: Artifact keys in production order: inputs (spec, plan), raw per-seat records
#: (transcript, votes), derived rulings (decision, stopping, outcome), then the
#: run's integrity digests, event log, budgets and meta. ``artifact_map`` walks
#: this tuple, so a key without a matching ``CouncilResult`` field fails closed.
ARTIFACT_KEYS: tuple[str, ...] = (
    "spec",
    "plan",
    "transcript",
    "votes",
    "decision",
    "stopping",
    "outcome",
    "integrity",
    "events",
    "budgets",
    "meta",
)

#: ``max_rounds`` runs exactly ``limit`` rounds. ``consensus`` stops at the first
#: round whose cast ballots are unanimous, and otherwise runs to ``limit``.
STOPPING_KINDS: tuple[str, ...] = ("max_rounds", "consensus")


class CouncilSpecError(ValueError):
    """A CouncilSpec, builder input or run argument is invalid."""


class DecisionStatus(str, Enum):
    """Ruling of the council on the proposal; ``value`` is what the CLI prints."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    UNDECIDED = "undecided"
    # Member names used by the IMP-0326-era module; same members, kept as aliases.
    ADOPT = "accepted"
    REJECT = "rejected"
    PARK = "undecided"


class VoteValue(str, Enum):
    FOR = "for"
    AGAINST = "against"
    ABSTAIN = "abstain"


#: Stance vocabulary accepted by ``add_participant`` and how each stance votes.
STANCE_VOTES: Mapping[str, VoteValue] = {
    "support": VoteValue.FOR,
    "for": VoteValue.FOR,
    "oppose": VoteValue.AGAINST,
    "against": VoteValue.AGAINST,
    "neutral": VoteValue.ABSTAIN,
    "abstain": VoteValue.ABSTAIN,
}


# --------------------------------------------------------------------------- spec


@dataclass(frozen=True)
class Participant:
    """One seat: who speaks, in what role, and the stance it argues and votes."""

    participant_id: str
    role: str
    stance: str

    def vote(self) -> VoteValue:
        try:
            return STANCE_VOTES[self.stance]
        except KeyError:
            raise CouncilSpecError(
                f"participant {self.participant_id!r} has unknown stance {self.stance!r}; "
                f"expected one of {sorted(STANCE_VOTES)}"
            ) from None


@dataclass(frozen=True)
class StoppingRule:
    kind: str = "max_rounds"
    limit: int = 1


@dataclass(frozen=True)
class CouncilSpec:
    """Immutable description of a council run (validated by :func:`validate_spec`)."""

    spec_id: str
    question: str
    charter: str = ""
    participants: tuple[Participant, ...] = ()
    stopping: StoppingRule = field(default_factory=StoppingRule)

    @property
    def seats(self) -> tuple[str, ...]:
        """Participant ids in speaking order (the IMP-0326-era ``seats`` view)."""
        return tuple(p.participant_id for p in self.participants)

    @property
    def rounds(self) -> int:
        """Upper bound on rounds (the IMP-0326-era ``rounds`` view)."""
        return self.stopping.limit

    @classmethod
    def from_seats(
        cls,
        question: str,
        seats: list[str] | tuple[str, ...],
        rounds: int = 2,
        spec_id: str | None = None,
    ) -> "CouncilSpec":
        """Legacy constructor: each seat is its own role and supports the proposal."""
        builder = CouncilSpecBuilder().question(question).seats(seats).rounds(rounds)
        if spec_id is not None:
            builder.spec_id(spec_id)
        return builder.build()


def _default_spec_id(question: str) -> str:
    return "spec-" + hashlib.sha256(question.encode("utf-8")).hexdigest()[:12]


def validate_spec(spec: Any) -> CouncilSpec:
    """Fail closed on anything that is not a well-formed :class:`CouncilSpec`."""
    if type(spec) is not CouncilSpec:
        raise CouncilSpecError(f"expected CouncilSpec, got {type(spec)!r}")
    if not isinstance(spec.spec_id, str) or not spec.spec_id.strip():
        raise CouncilSpecError("spec_id must be a non-empty string")
    if not isinstance(spec.question, str) or not spec.question.strip():
        raise CouncilSpecError("question must be a non-empty string")
    if not isinstance(spec.charter, str):
        raise CouncilSpecError("charter must be a string")
    if not spec.participants:
        raise CouncilSpecError("a council needs at least one participant")
    seen: set[str] = set()
    for participant in spec.participants:
        if type(participant) is not Participant:
            raise CouncilSpecError(f"participants must be Participant, got {type(participant)!r}")
        if not participant.participant_id.strip():
            raise CouncilSpecError("participant_id must be a non-empty string")
        if not participant.role.strip():
            raise CouncilSpecError(f"participant {participant.participant_id!r} has an empty role")
        if participant.participant_id in seen:
            raise CouncilSpecError(f"duplicate participant_id {participant.participant_id!r}")
        seen.add(participant.participant_id)
        participant.vote()  # raises on an unknown stance
    rule = spec.stopping
    if type(rule) is not StoppingRule:
        raise CouncilSpecError(f"stopping must be StoppingRule, got {type(rule)!r}")
    if rule.kind not in STOPPING_KINDS:
        raise CouncilSpecError(f"unknown stopping kind {rule.kind!r}; expected one of {STOPPING_KINDS}")
    if isinstance(rule.limit, bool) or not isinstance(rule.limit, int) or rule.limit < 1:
        raise CouncilSpecError(f"stopping limit must be an integer >= 1, got {rule.limit!r}")
    return spec


class CouncilSpecBuilder:
    """Fluent builder; every setter returns the builder and validates eagerly."""

    def __init__(self) -> None:
        self._spec_id: str | None = None
        self._question: str = ""
        self._charter: str = ""
        self._participants: list[Participant] = []
        self._stopping = StoppingRule("max_rounds", 2)

    def spec_id(self, spec_id: str) -> "CouncilSpecBuilder":
        if not isinstance(spec_id, str) or not spec_id.strip():
            raise CouncilSpecError("spec_id must be a non-empty string")
        self._spec_id = spec_id.strip()
        return self

    def question(self, text: str) -> "CouncilSpecBuilder":
        if not isinstance(text, str) or not text.strip():
            raise CouncilSpecError("question must be a non-empty string")
        self._question = text.strip()
        return self

    def charter(self, text: str) -> "CouncilSpecBuilder":
        if not isinstance(text, str):
            raise CouncilSpecError("charter must be a string")
        self._charter = text.strip()
        return self

    def add_participant(self, participant_id: str, role: str, stance: str) -> "CouncilSpecBuilder":
        if not isinstance(participant_id, str) or not participant_id.strip():
            raise CouncilSpecError("participant_id must be a non-empty string")
        if not isinstance(role, str) or not role.strip():
            raise CouncilSpecError(f"participant {participant_id!r} needs a non-empty role")
        if stance not in STANCE_VOTES:
            raise CouncilSpecError(
                f"participant {participant_id!r} has unknown stance {stance!r}; "
                f"expected one of {sorted(STANCE_VOTES)}"
            )
        if any(p.participant_id == participant_id for p in self._participants):
            raise CouncilSpecError(f"duplicate participant_id {participant_id!r}")
        self._participants.append(Participant(participant_id.strip(), role.strip(), stance))
        return self

    def seats(self, seats: list[str] | tuple[str, ...]) -> "CouncilSpecBuilder":
        """Legacy shorthand: each seat id is its own role and supports the proposal."""
        self._participants = []
        for seat in seats:
            self.add_participant(str(seat), str(seat), "support")
        return self

    def stopping(self, kind: str, n: int) -> "CouncilSpecBuilder":
        if kind not in STOPPING_KINDS:
            raise CouncilSpecError(f"unknown stopping kind {kind!r}; expected one of {STOPPING_KINDS}")
        if isinstance(n, bool) or not isinstance(n, int) or n < 1:
            raise CouncilSpecError(f"stopping limit must be an integer >= 1, got {n!r}")
        self._stopping = StoppingRule(kind, n)
        return self

    def rounds(self, n: int) -> "CouncilSpecBuilder":
        """Legacy shorthand for ``stopping("max_rounds", n)``."""
        return self.stopping("max_rounds", n)

    def build(self) -> CouncilSpec:
        if not self._question:
            raise CouncilSpecError("question is required before build()")
        spec = CouncilSpec(
            spec_id=self._spec_id or _default_spec_id(self._question),
            question=self._question,
            charter=self._charter,
            participants=tuple(self._participants),
            stopping=self._stopping,
        )
        return validate_spec(spec)


# ------------------------------------------------------------------- result types


@dataclass(frozen=True)
class RoundPlan:
    round_index: int
    speakers: tuple[str, ...]


@dataclass(frozen=True)
class Plan:
    """Schedule derived from the spec before any turn is taken."""

    stopping_kind: str
    max_rounds: int
    speaking_order: tuple[str, ...]
    ballots_per_round: int
    schedule: tuple[RoundPlan, ...]


@dataclass(frozen=True)
class Turn:
    round_index: int
    participant_id: str
    role: str
    stance: str
    text: str
    tokens: int


@dataclass
class Transcript:
    """Ordered per-seat turns; iterable so ``list(result.transcript)`` still works."""

    turns: list[Turn] = field(default_factory=list)

    def __iter__(self) -> Iterator[Turn]:
        return iter(self.turns)

    def __len__(self) -> int:
        return len(self.turns)

    def by_round(self, round_index: int) -> list[Turn]:
        return [t for t in self.turns if t.round_index == round_index]

    def by_participant(self, participant_id: str) -> list[Turn]:
        return [t for t in self.turns if t.participant_id == participant_id]


@dataclass(frozen=True)
class Ballot:
    participant_id: str
    role: str
    vote: VoteValue
    round_index: int
    stance: str


@dataclass
class VoteTally:
    """Ballots of one round with their counts; every ballot weighs one."""

    for_count: int
    against_count: int
    abstain_count: int = 0
    ballots: list[Ballot] = field(default_factory=list)
    round_index: int = 0

    @property
    def cast_count(self) -> int:
        return self.for_count + self.against_count

    def unanimous(self) -> bool:
        return self.cast_count > 0 and (self.for_count == 0 or self.against_count == 0)


#: IMP-0326-era name for the tally type.
Votes = VoteTally


@dataclass
class Decision:
    status: DecisionStatus
    deciding_rule: str
    summary: str
    for_count: int = 0
    against_count: int = 0
    abstain_count: int = 0
    margin: int = 0

    @property
    def rationale(self) -> str:
        """IMP-0326-era name for ``summary``."""
        return self.summary


@dataclass
class Stopping:
    rounds_completed: int
    reason: str
    kind: str = "max_rounds"
    limit: int = 1


@dataclass(frozen=True)
class Outcome:
    """What the council publishes; ``accepted`` follows ``decision.status`` only."""

    accepted: bool
    status: DecisionStatus
    proposal: str
    statement: str


@dataclass(frozen=True)
class Integrity:
    """Content digests over the canonical JSON of each recorded section."""

    algorithm: str
    spec_digest: str
    transcript_digest: str
    votes_digest: str
    decision_digest: str
    result_digest: str


@dataclass(frozen=True)
class Event:
    seq: int
    kind: str
    round_index: int | None
    participant_id: str | None
    detail: str


@dataclass
class EventLog:
    entries: list[Event] = field(default_factory=list)

    def __iter__(self) -> Iterator[Event]:
        return iter(self.entries)

    def __len__(self) -> int:
        return len(self.entries)

    def record(
        self,
        kind: str,
        *,
        round_index: int | None = None,
        participant_id: str | None = None,
        detail: str = "",
    ) -> Event:
        event = Event(len(self.entries) + 1, kind, round_index, participant_id, detail)
        self.entries.append(event)
        return event


@dataclass
class Budgets:
    turns: int
    tokens: int = 0
    rounds: int = 0
    participants: int = 0
    ballots: int = 0


@dataclass
class Meta:
    run_id: str
    spec_question: str
    engine: str = ENGINE_NAME
    engine_version: str = ENGINE_VERSION
    spec_id: str = ""
    participant_count: int = 0
    rounds_planned: int = 0


@dataclass
class CouncilResult:
    """Typed result; field order matches :data:`ARTIFACT_KEYS`."""

    spec: CouncilSpec
    plan: Plan
    transcript: Transcript
    votes: VoteTally
    decision: Decision
    stopping: Stopping
    outcome: Outcome
    integrity: Integrity
    events: EventLog
    budgets: Budgets
    meta: Meta

    def artifact_map(self) -> dict[str, Any]:
        """Typed artifacts keyed by :data:`ARTIFACT_KEYS`, in that order."""
        return {key: getattr(self, key) for key in ARTIFACT_KEYS}

    def to_payload(self) -> dict[str, Any]:
        """JSON-ready view of :meth:`artifact_map` (what the CLI prints)."""
        return jsonable(self.artifact_map())


@dataclass
class Parity:
    sdk_keys: list[str]
    cli_keys: list[str]
    sdk_minus_cli: list[str]
    cli_minus_sdk: list[str]
    equal: bool


# ------------------------------------------------------------------------ engine

_STANCE_PHRASES: Mapping[VoteValue, str] = {
    VoteValue.FOR: "supports the proposal and casts a ballot for it",
    VoteValue.AGAINST: "opposes the proposal and casts a ballot against it",
    VoteValue.ABSTAIN: "takes no position and abstains",
}


def _estimate_tokens(text: str) -> int:
    """Deterministic ~4-characters-per-token estimate; never below one."""
    return max(1, (len(text) + 3) // 4)


def _build_plan(spec: CouncilSpec) -> Plan:
    order = spec.seats
    schedule = tuple(RoundPlan(r, order) for r in range(1, spec.stopping.limit + 1))
    return Plan(
        stopping_kind=spec.stopping.kind,
        max_rounds=spec.stopping.limit,
        speaking_order=order,
        ballots_per_round=len(order),
        schedule=schedule,
    )


def _compose_turn(participant: Participant, round_index: int, rounds_planned: int, question: str) -> Turn:
    phrase = _STANCE_PHRASES[participant.vote()]
    text = (
        f"[round {round_index}/{rounds_planned}] {participant.participant_id} "
        f"({participant.role}) {phrase}: {question}"
    )
    return Turn(
        round_index=round_index,
        participant_id=participant.participant_id,
        role=participant.role,
        stance=participant.stance,
        text=text,
        tokens=_estimate_tokens(text),
    )


def _cast_ballot(participant: Participant, round_index: int) -> Ballot:
    return Ballot(
        participant_id=participant.participant_id,
        role=participant.role,
        vote=participant.vote(),
        round_index=round_index,
        stance=participant.stance,
    )


def _tally(ballots: list[Ballot], round_index: int) -> VoteTally:
    counts = Counter(b.vote for b in ballots)
    return VoteTally(
        for_count=counts[VoteValue.FOR],
        against_count=counts[VoteValue.AGAINST],
        abstain_count=counts[VoteValue.ABSTAIN],
        ballots=list(ballots),
        round_index=round_index,
    )


def _decide(votes: VoteTally) -> Decision:
    """Unweighted majority over the cast ballots of one tally.

    Every ballot counts once whatever the seat's role; abstentions are recorded
    but do not move the count. A tie, including no cast ballots at all, is not a
    mandate either way and stays undecided.
    """
    margin = votes.for_count - votes.against_count
    counts = f"{votes.for_count} for, {votes.against_count} against, {votes.abstain_count} abstain"
    if margin > 0:
        status, rule = DecisionStatus.ACCEPTED, "unweighted-majority"
        summary = f"{counts}: proposal accepted by unweighted majority (+{margin})"
    elif margin < 0:
        status, rule = DecisionStatus.REJECTED, "unweighted-majority"
        summary = f"{counts}: proposal rejected by unweighted majority ({margin})"
    else:
        status, rule = DecisionStatus.UNDECIDED, "tie-no-majority"
        summary = f"{counts}: no majority, proposal undecided"
    return Decision(
        status=status,
        deciding_rule=rule,
        summary=summary,
        for_count=votes.for_count,
        against_count=votes.against_count,
        abstain_count=votes.abstain_count,
        margin=margin,
    )


def _stop_reason(rule: StoppingRule, round_index: int, tally: VoteTally) -> str | None:
    """The reason to stop after ``round_index``, or None to run another round."""
    if rule.kind == "consensus" and tally.unanimous():
        return f"consensus reached in round {round_index}"
    if round_index >= rule.limit:
        if rule.kind == "consensus":
            return f"max_rounds {rule.limit} reached without consensus"
        return f"max_rounds {rule.limit} reached"
    return None


def _outcome(spec: CouncilSpec, decision: Decision) -> Outcome:
    accepted = decision.status is DecisionStatus.ACCEPTED
    if accepted:
        statement = f"Proposal accepted: {spec.question}"
    elif decision.status is DecisionStatus.REJECTED:
        statement = f"Proposal rejected: {spec.question}"
    else:
        statement = f"No decision reached: {spec.question}"
    return Outcome(accepted=accepted, status=decision.status, proposal=spec.question, statement=statement)


def _digest(obj: Any) -> str:
    canonical = json.dumps(jsonable(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _integrity(spec: CouncilSpec, transcript: Transcript, votes: VoteTally, decision: Decision) -> Integrity:
    parts = (_digest(spec), _digest(transcript), _digest(votes), _digest(decision))
    chain = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
    return Integrity("sha256", parts[0], parts[1], parts[2], parts[3], chain)


def execute_spec(spec: CouncilSpec, run_id: str = "run") -> CouncilResult:
    """Run the council described by ``spec`` deterministically.

    Rounds proceed in seat order. Every participant speaks once per round and
    casts one ballot per round; turns and ballots are appended per seat as they
    happen. The tally of the last completed round is the only input to
    ``_decide``; the run id is metadata and never touches the votes.
    """
    validate_spec(spec)
    if not isinstance(run_id, str) or not run_id.strip():
        raise CouncilSpecError("run_id must be a non-empty string")
    plan = _build_plan(spec)
    events = EventLog()
    transcript = Transcript()
    events.record(
        "council.opened",
        detail=(
            f"spec_id={spec.spec_id} participants={len(spec.participants)} "
            f"stopping={spec.stopping.kind}:{spec.stopping.limit}"
        ),
    )
    votes = _tally([], 0)
    rounds_completed = 0
    stop_reason = ""
    for round_plan in plan.schedule:
        r = round_plan.round_index
        events.record("round.opened", round_index=r, detail=f"speakers={len(round_plan.speakers)}")
        round_ballots: list[Ballot] = []
        for participant in spec.participants:
            turn = _compose_turn(participant, r, plan.max_rounds, spec.question)
            transcript.turns.append(turn)
            events.record(
                "turn.recorded",
                round_index=r,
                participant_id=participant.participant_id,
                detail=f"role={participant.role} tokens={turn.tokens}",
            )
            ballot = _cast_ballot(participant, r)
            round_ballots.append(ballot)
            events.record(
                "ballot.cast",
                round_index=r,
                participant_id=participant.participant_id,
                detail=f"vote={ballot.vote.value}",
            )
        votes = _tally(round_ballots, r)
        rounds_completed = r
        events.record(
            "round.closed",
            round_index=r,
            detail=f"for={votes.for_count} against={votes.against_count} abstain={votes.abstain_count}",
        )
        reason = _stop_reason(spec.stopping, r, votes)
        if reason is not None:
            stop_reason = reason
            events.record("stopping.satisfied", round_index=r, detail=reason)
            break
    decision = _decide(votes)
    events.record(
        "decision.recorded",
        detail=f"status={decision.status.value} rule={decision.deciding_rule} margin={decision.margin}",
    )
    stopping = Stopping(
        rounds_completed=rounds_completed,
        reason=stop_reason,
        kind=spec.stopping.kind,
        limit=spec.stopping.limit,
    )
    outcome = _outcome(spec, decision)
    integrity = _integrity(spec, transcript, votes, decision)
    budgets = Budgets(
        turns=len(transcript),
        tokens=sum(t.tokens for t in transcript),
        rounds=rounds_completed,
        participants=len(spec.participants),
        ballots=len(votes.ballots),
    )
    meta = Meta(
        run_id=run_id,
        spec_question=spec.question,
        spec_id=spec.spec_id,
        participant_count=len(spec.participants),
        rounds_planned=plan.max_rounds,
    )
    events.record("council.closed", detail=f"run_id={run_id} turns={budgets.turns} tokens={budgets.tokens}")
    return CouncilResult(
        spec=spec,
        plan=plan,
        transcript=transcript,
        votes=votes,
        decision=decision,
        stopping=stopping,
        outcome=outcome,
        integrity=integrity,
        events=events,
        budgets=budgets,
        meta=meta,
    )


# --------------------------------------------------------------- serialisation


def _is_dataclass_instance(obj: Any) -> bool:
    return dataclasses.is_dataclass(obj) and not isinstance(obj, type)


def jsonable(obj: Any) -> Any:
    """Convert dataclasses / enums / containers to JSON-ready values, depth first.

    Enums are checked first: a ``str``-mixin enum member is also a ``str`` and
    also has a ``__dict__``, and only its ``value`` is the intended output.
    Unsupported types raise rather than being stringified.
    """
    if isinstance(obj, Enum):
        return obj.value
    if _is_dataclass_instance(obj):
        return {f.name: jsonable(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, dict):
        return {str(k): jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [jsonable(x) for x in obj]
    if isinstance(obj, (set, frozenset)):
        return sorted((jsonable(x) for x in obj), key=repr)
    if isinstance(obj, Path):
        return obj.as_posix()
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if hasattr(obj, "__dict__"):
        return {k: jsonable(v) for k, v in vars(obj).items() if not k.startswith("_")}
    raise TypeError(f"jsonable: unsupported type {type(obj).__name__}")


def assert_typed_result(result: Any) -> None:
    """Raise TypeError unless ``result`` and every artifact value are typed objects."""
    if type(result) is not CouncilResult:
        raise TypeError(f"expected CouncilResult, got {type(result)!r}")
    if type(result.decision) is not Decision:
        raise TypeError("decision is not Decision")
    if type(result.decision.status) is not DecisionStatus:
        raise TypeError("decision.status is not DecisionStatus")
    if type(result.votes) is not VoteTally:
        raise TypeError("votes is not VoteTally")
    if type(result.outcome) is not Outcome:
        raise TypeError("outcome is not Outcome")
    for key, value in result.artifact_map().items():
        if not _is_dataclass_instance(value):
            raise TypeError(f"artifact {key!r} is not a dataclass instance: {type(value)!r}")
    for ballot in result.votes.ballots:
        if type(ballot) is not Ballot or type(ballot.vote) is not VoteValue:
            raise TypeError("votes.ballots must be Ballot objects with VoteValue votes")
    for turn in result.transcript.turns:
        if type(turn) is not Turn:
            raise TypeError("transcript.turns must be Turn objects")


def sdk_reachable_keys(result: CouncilResult) -> set[str]:
    """Artifact keys reachable through the typed SDK result."""
    return set(result.artifact_map())


def cli_inspect_payload(result: CouncilResult, hide: list[str] | None = None) -> dict[str, Any]:
    """The JSON object the CLI ``inspect`` prints; ``hide`` drops top-level keys."""
    payload = result.to_payload()
    for key in hide or []:
        payload.pop(key, None)
    return payload


#: IMP-0326-era private name for :func:`cli_inspect_payload`.
_cli_view = cli_inspect_payload


def surface_parity(result: CouncilResult, hide_from_cli: list[str] | None = None) -> Parity:
    """Set difference in both directions between SDK-reachable and CLI-reachable keys."""
    sdk = sdk_reachable_keys(result)
    cli = set(cli_inspect_payload(result, hide_from_cli))
    return Parity(
        sdk_keys=sorted(sdk),
        cli_keys=sorted(cli),
        sdk_minus_cli=sorted(sdk - cli),
        cli_minus_sdk=sorted(cli - sdk),
        equal=sdk == cli,
    )


# ---------------------------------------------------------------------- facade


class CouncilSDK:
    """Programmatic surface: build a spec, execute it, inspect, persist and load."""

    engine = ENGINE_NAME

    def builder(self) -> CouncilSpecBuilder:
        return CouncilSpecBuilder()

    def build_fixture(self) -> CouncilSpec:
        """Known-good unanimous council: three voting seats, two rounds."""
        return (
            CouncilSpecBuilder()
            .spec_id("imp-0326-fixture")
            .question("Should the fixture proposal be accepted?")
            .charter(
                "Parity fixture: three seats that all support the proposal deliberate "
                "for two rounds so every artifact section is populated."
            )
            .add_participant("advocate", "advocate", "support")
            .add_participant("domain_expert", "domain_expert", "support")
            .add_participant("juror", "juror", "support")
            .stopping("max_rounds", 2)
            .build()
        )

    def execute(self, spec: CouncilSpec, run_id: str) -> CouncilResult:
        return execute_spec(spec, run_id=run_id)

    def inspect(self, result: CouncilResult) -> dict[str, Any]:
        return cli_inspect_payload(result)

    def persist(self, result: CouncilResult, run_dir: Path) -> Path:
        assert_typed_result(result)
        run_dir = Path(run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        path = run_dir / RESULT_FILENAME
        path.write_text(
            json.dumps(cli_inspect_payload(result), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return path

    def load(self, run_dir: Path) -> dict[str, Any]:
        path = Path(run_dir) / RESULT_FILENAME
        if not path.is_file():
            raise FileNotFoundError(f"no {RESULT_FILENAME} under {run_dir}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"{path} does not hold a JSON object")
        return data


# ------------------------------------------------------------------------- CLI


def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="council-sdk", description="Inspect persisted council results.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    inspect_p = sub.add_parser("inspect", help="print the persisted council-result.json as one JSON object")
    inspect_p.add_argument("--run-dir", required=True, help="directory holding council-result.json")
    inspect_p.add_argument("--hide", action="append", default=[], metavar="KEY", help="omit a top-level key")
    sub.add_parser("keys", help="print ARTIFACT_KEYS")
    args = parser.parse_args(argv)
    if args.cmd == "inspect":
        data = CouncilSDK().load(Path(args.run_dir))
        for key in args.hide or []:
            data.pop(key, None)
        print(json.dumps(data, sort_keys=True))
        return 0
    if args.cmd == "keys":
        print(json.dumps(list(ARTIFACT_KEYS)))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(_cli())
