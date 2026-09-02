"""CNL-0021 config-side replacement protocol and duplicate-independence detector.

This is the executable design: a bounded step machine plus a label-blind
canonical-model grouping. ADV-0136 attests the same question from the
response side; this module never reads transport logs.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Iterable

MAX_STEPS = 64
TERMINAL = frozenset(
    {
        "COMPLETE",
        "REPLACED-AND-CONTINUED",
        "DEGRADED-NO-REPLACEMENT",
        "ABORTED-QUORUM",
        "HUNG",
    }
)
HONEST_TERMINAL = frozenset(
    {
        "COMPLETE",
        "REPLACED-AND-CONTINUED",
        "DEGRADED-NO-REPLACEMENT",
        "ABORTED-QUORUM",
    }
)

_DATE_OR_BUILD = re.compile(r"[-_](\d{8}|\d{4}-\d{2}-\d{2}|latest|preview)$")

# Aliases that survive date-stripping. Keys and values are already lowercase.
MODEL_ALIASES = {
    "chatgpt-4o": "gpt-4o",
    "gpt4o": "gpt-4o",
    "claude-3-opus": "claude-opus-3",
    "claude-3.5-sonnet": "claude-sonnet-3.5",
    "claude-3-5-sonnet": "claude-sonnet-3.5",
}


def canonical_model(model: str | None) -> str | None:
    """Strip vendor prefixes and date stamps; map known aliases.

    gpt-4o must not collapse to gpt-4, and gpt-4.1 must stay distinct from gpt-4o.
    """
    if model is None:
        return None
    s = str(model).strip().lower()
    if not s or s in {"unknown", "n/a", "none", "-"}:
        return None
    if "/" in s:
        s = s.rsplit("/", 1)[-1]
    while True:
        nxt = _DATE_OR_BUILD.sub("", s)
        if nxt == s:
            break
        s = nxt
    return MODEL_ALIASES.get(s, s)


@dataclass
class Seat:
    seat_id: str
    role: str
    vendor: str
    model: str
    alive: bool = True
    declared_independent: bool = True


@dataclass
class Ballot:
    round_id: int
    seat_id: str
    option: str


@dataclass
class Idea:
    idea_id: str
    originator_seat_id: str
    round_id: int
    text: str


@dataclass
class Finding:
    code: str
    seats: tuple[str, ...]
    detail: str


@dataclass
class Council:
    seats: list[Seat]
    ballots: list[Ballot] = field(default_factory=list)
    ideas: list[Idea] = field(default_factory=list)
    round_id: int = 1
    status: str = "RUNNING"
    quorum: int = 2
    events: list[dict] = field(default_factory=list)
    waiting_for: str | None = None
    replacement_of: dict[str, str] = field(default_factory=dict)
    inherit_votes: bool = False
    reuse_seat_id: bool = False
    hang_on_death: bool = False
    steps: int = 0
    target_rounds: int = 2

    def seat(self, seat_id: str) -> Seat | None:
        for s in self.seats:
            if s.seat_id == seat_id:
                return s
        return None

    def living(self) -> list[Seat]:
        return [s for s in self.seats if s.alive]


def duplicate_pairs(seats: Iterable[Seat]) -> list[Finding]:
    """CONFIG-side independence: same canonical model is not independent evidence.

    Role labels, seat ids, vendor strings, and declared_independent are ignored
    as grouping keys. Missing canonical model -> UNATTESTED (fail-closed for
    that seat; it cannot count as independent evidence).
    """
    findings: list[Finding] = []
    groups: dict[str, list[Seat]] = defaultdict(list)
    for s in seats:
        key = canonical_model(s.model)
        if key is None:
            findings.append(
                Finding(
                    "UNATTESTED",
                    (s.seat_id,),
                    "missing-or-empty-model; cannot count as independent evidence",
                )
            )
            continue
        groups[key].append(s)
    for key, members in sorted(groups.items()):
        if len(members) < 2:
            continue
        ids = tuple(sorted(m.seat_id for m in members))
        findings.append(
            Finding(
                "DUPLICATE-INDEPENDENCE",
                ids,
                f"canonical_model={key} shared by {len(members)} seats",
            )
        )
    return findings


def detect_by_role(seats: Iterable[Seat]) -> list[Finding]:
    """Mutant checker: groups by role label. Misses same-model different-role collusion."""
    groups: dict[str, list[Seat]] = defaultdict(list)
    for s in seats:
        groups[s.role].append(s)
    out: list[Finding] = []
    for role, members in sorted(groups.items()):
        if len(members) < 2:
            continue
        out.append(
            Finding(
                "DUPLICATE-INDEPENDENCE",
                tuple(sorted(m.seat_id for m in members)),
                f"role={role}",
            )
        )
    return out


def inherited_ballots(council: Council, dead_id: str, replacement_id: str) -> list[Ballot]:
    """Ballots attributed to the replacement for rounds the dead seat attended."""
    dead_rounds = {b.round_id for b in council.ballots if b.seat_id == dead_id}
    return [
        b
        for b in council.ballots
        if b.seat_id == replacement_id and b.round_id in dead_rounds
    ]


def idea_originators(council: Council) -> dict[str, str]:
    return {i.idea_id: i.originator_seat_id for i in council.ideas}


def _log(council: Council, kind: str, **payload: object) -> None:
    rec = {"kind": kind, "round_id": council.round_id, "step": council.steps}
    rec.update(payload)
    council.events.append(rec)


def _alive_ids_in_order(council: Council) -> list[str]:
    return [s.seat_id for s in council.seats if s.alive]


def _cast(council: Council, seat_id: str, option: str) -> None:
    council.ballots.append(Ballot(council.round_id, seat_id, option))
    _log(council, "ballot", seat_id=seat_id, option=option)


def _kill(council: Council, seat_id: str, reason: str) -> None:
    s = council.seat(seat_id)
    if s is None or not s.alive:
        return
    s.alive = False
    council.waiting_for = seat_id
    _log(council, "death", seat_id=seat_id, reason=reason)


def _seat_replacement(council: Council, dead_id: str, candidate: Seat | None) -> None:
    council.waiting_for = None
    living = council.living()
    if candidate is None:
        if len(living) >= council.quorum:
            council.status = "DEGRADED-NO-REPLACEMENT"
            _log(council, "degraded", dead_id=dead_id, living=len(living))
        else:
            council.status = "ABORTED-QUORUM"
            _log(council, "aborted", dead_id=dead_id, living=len(living))
        return
    new_id = dead_id if council.reuse_seat_id else candidate.seat_id
    if new_id == dead_id and not council.reuse_seat_id:
        new_id = candidate.seat_id
    replacement = Seat(
        seat_id=new_id,
        role=candidate.role,
        vendor=candidate.vendor,
        model=candidate.model,
        alive=True,
        declared_independent=candidate.declared_independent,
    )
    if council.reuse_seat_id:
        dead = council.seat(dead_id)
        if dead is not None:
            dead.alive = True
            dead.vendor = candidate.vendor
            dead.model = candidate.model
            replacement = dead
            new_id = dead_id
    else:
        council.seats.append(replacement)
    council.replacement_of[new_id] = dead_id
    if council.inherit_votes:
        copies = [
            Ballot(b.round_id, new_id, b.option)
            for b in council.ballots
            if b.seat_id == dead_id
        ]
        council.ballots.extend(copies)
        _log(council, "vote-inheritance-mutant", dead_id=dead_id, copies=len(copies))
    _log(council, "replacement-seated", dead_id=dead_id, replacement_id=new_id)
    council.status = "RUNNING"


def step(council: Council, script: list[dict], cursor: list[int]) -> None:
    """Advance one bounded step. Death never waits unbounded on a dead seat."""
    council.steps += 1
    if council.status != "RUNNING":
        return
    if council.hang_on_death:
        dead_waiting = council.seat(council.waiting_for) if council.waiting_for else None
        if dead_waiting is not None and not dead_waiting.alive:
            _log(council, "hang-wait", seat_id=dead_waiting.seat_id)
            return
    if cursor[0] < len(script):
        ev = script[cursor[0]]
        cursor[0] += 1
        kind = ev["kind"]
        if kind == "ballot":
            _cast(council, ev["seat_id"], ev["option"])
        elif kind == "idea":
            council.ideas.append(
                Idea(ev["idea_id"], ev["seat_id"], council.round_id, ev["text"])
            )
            _log(council, "idea", idea_id=ev["idea_id"], seat_id=ev["seat_id"])
        elif kind == "death":
            _kill(council, ev["seat_id"], ev.get("reason", "crash"))
            if council.hang_on_death:
                return
            _seat_replacement(council, ev["seat_id"], ev.get("replacement"))
        elif kind == "end-round":
            council.round_id += 1
            _log(council, "end-round")
            if council.round_id > council.target_rounds:
                if council.status == "RUNNING":
                    council.status = (
                        "REPLACED-AND-CONTINUED"
                        if council.replacement_of
                        else "COMPLETE"
                    )
        return
    if council.status == "RUNNING":
        council.status = (
            "REPLACED-AND-CONTINUED" if council.replacement_of else "COMPLETE"
        )


def run(
    council: Council,
    script: list[dict],
    max_steps: int = MAX_STEPS,
) -> Council:
    cursor = [0]
    while council.status == "RUNNING" and council.steps < max_steps:
        step(council, script, cursor)
    if council.status == "RUNNING":
        council.status = "HUNG"
        _log(council, "hung", steps=council.steps)
    return council


def hang_check(council: Council) -> Finding | None:
    if council.status == "HUNG":
        return Finding("HANG", tuple(), f"exceeded MAX_STEPS={MAX_STEPS}")
    if council.status not in HONEST_TERMINAL:
        return Finding("UNDEFINED-STATE", tuple(), council.status)
    return None


ReplacementPolicy = Callable[[Council, str], Seat | None]
