"""Coordinated-disclosure state machine with owner-gated public disclose."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class State(Enum):
    REPORTED = "reported"
    TRIAGED = "triaged"
    EMBARGOED = "embargoed"
    FIX_AVAILABLE = "fix_available"
    DISCLOSED = "disclosed"
    WITHDRAWN = "withdrawn"


STATES: tuple[State, ...] = (
    State.REPORTED,
    State.TRIAGED,
    State.EMBARGOED,
    State.FIX_AVAILABLE,
    State.DISCLOSED,
    State.WITHDRAWN,
)

LEGAL_TRANSITIONS: frozenset[tuple[State, State]] = frozenset(
    {
        (State.REPORTED, State.TRIAGED),
        (State.REPORTED, State.WITHDRAWN),
        (State.TRIAGED, State.EMBARGOED),
        (State.TRIAGED, State.FIX_AVAILABLE),
        (State.TRIAGED, State.DISCLOSED),
        (State.TRIAGED, State.WITHDRAWN),
        (State.EMBARGOED, State.FIX_AVAILABLE),
        (State.EMBARGOED, State.DISCLOSED),
        (State.EMBARGOED, State.WITHDRAWN),
        (State.FIX_AVAILABLE, State.DISCLOSED),
        (State.FIX_AVAILABLE, State.WITHDRAWN),
        (State.FIX_AVAILABLE, State.EMBARGOED),
    }
)


class IllegalTransition(Exception):
    def __init__(self, message: str, code: str = "illegal-transition") -> None:
        super().__init__(message)
        self.code = code


class OwnerGated(Exception):
    def __init__(self, message: str, code: str = "owner-gated") -> None:
        super().__init__(message)
        self.code = code


def legal_transition_edges() -> list[dict[str, str]]:
    return [{"from": a.value, "to": b.value} for a, b in sorted(LEGAL_TRANSITIONS, key=lambda x: (x[0].value, x[1].value))]


@dataclass
class Advisory:
    id: str
    package_id: str
    detail: str
    state: State = State.REPORTED
    actor: str = "reporter"


@dataclass
class EventLog:
    events: list[dict[str, str]] = field(default_factory=list)

    def add(self, *, advisory_id: str, frm: str, to: str, actor: str) -> None:
        self.events.append(
            {
                "advisory_id": advisory_id,
                "from": frm,
                "to": to,
                "actor": actor,
            }
        )

    def dump_text(self) -> str:
        # Lifecycle names only — never advisory detail.
        lines = [f"{e['advisory_id']} {e['from']}->{e['to']} actor={e['actor']}" for e in self.events]
        return "\n".join(lines)


class DisclosureRegistry:
    def __init__(self) -> None:
        self._items: dict[str, Advisory] = {}
        self.log = EventLog()

    def create(self, package_id: str, detail: str, actor: str = "reporter") -> Advisory:
        rec = Advisory(id=str(uuid.uuid4()), package_id=package_id, detail=detail, actor=actor)
        self._items[rec.id] = rec
        self.log.add(advisory_id=rec.id, frm="none", to=rec.state.value, actor=actor)
        return rec

    def get(self, aid: str) -> Advisory:
        return self._items[aid]

    def transition(
        self,
        aid: str,
        target: State,
        actor: str = "triager",
        owner_approved: bool = False,
    ) -> Advisory:
        rec = self._items[aid]
        if rec.state is target:
            if (rec.state, target) not in LEGAL_TRANSITIONS:
                raise IllegalTransition(f"{rec.state.value}->{target.value}", code="illegal-transition")
            return rec
        if (rec.state, target) not in LEGAL_TRANSITIONS:
            raise IllegalTransition(f"{rec.state.value}->{target.value}", code="illegal-transition")
        if target is State.DISCLOSED and not owner_approved:
            raise OwnerGated("disclose requires owner approval", code="owner-gated")
        frm = rec.state
        rec.state = target
        self.log.add(advisory_id=rec.id, frm=frm.value, to=target.value, actor=actor)
        return rec
