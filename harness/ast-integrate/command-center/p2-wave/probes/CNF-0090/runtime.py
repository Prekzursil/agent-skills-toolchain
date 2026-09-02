#!/usr/bin/env python3
"""Deterministic council runtime with point-of-use role enforcement.

Mandates are checked at the action call site (speak/vote/veto), not as prompt
labels. When enforce=False, mandates are stripped and every occupant may act:
that is the role-collapse control. Replacement copies the seat's mandate and
clears the predecessor's position and ballots.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Mandate:
    speaking: bool
    vote: bool
    veto: bool

    def as_dict(self) -> dict[str, bool]:
        return {"speaking": self.speaking, "vote": self.vote, "veto": self.veto}


@dataclass
class Seat:
    seat_id: str
    occupant_id: str
    role_id: str
    mandate: Mandate
    position: str | None = None
    ballots: list[str] = field(default_factory=list)


@dataclass
class Event:
    seq: int
    config: str
    occupant_id: str
    seat_id: str
    role_id: str
    action: str
    accepted: bool
    reason: str
    payload: str
    enforced_at: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class Council:
    def __init__(self, config_id: str, enforce: bool, seats: list[Seat]) -> None:
        self.config_id = config_id
        self.enforce = enforce
        self.seats: dict[str, Seat] = {s.seat_id: s for s in seats}
        self.events: list[Event] = []
        self.replacements: list[dict[str, Any]] = []
        self._seq = 0

    def _allowed(self, seat: Seat, action: str) -> tuple[bool, str]:
        if action == "replace":
            return True, "replace-ok"
        if not self.enforce:
            return True, "mandates-stripped"
        if action == "speak":
            if seat.mandate.speaking:
                return True, "speaking-granted"
            return False, "speaking-rights-denied"
        if action == "vote":
            if seat.mandate.vote:
                return True, "vote-granted"
            return False, "vote-rights-denied"
        if action == "veto":
            if seat.mandate.veto:
                return True, "veto-granted"
            return False, "veto-rights-denied"
        raise ValueError(f"unknown action {action}")

    def _emit(
        self,
        seat: Seat,
        action: str,
        accepted: bool,
        reason: str,
        payload: str,
    ) -> Event:
        self._seq += 1
        ev = Event(
            seq=self._seq,
            config=self.config_id,
            occupant_id=seat.occupant_id,
            seat_id=seat.seat_id,
            role_id=seat.role_id,
            action=action,
            accepted=accepted,
            reason=reason,
            payload=payload,
            enforced_at="runtime" if self.enforce else "stripped",
        )
        self.events.append(ev)
        return ev

    def attempt(self, seat_id: str, action: str, payload: str) -> Event:
        seat = self.seats[seat_id]
        ok, reason = self._allowed(seat, action)
        if ok:
            if action == "vote":
                seat.position = payload
                seat.ballots.append(payload)
            elif action == "veto":
                seat.position = f"VETO:{payload}"
            elif action == "speak" and payload.startswith("POSITION:"):
                seat.position = payload.split("POSITION:", 1)[1]
        return self._emit(seat, action, ok, reason, payload)

    def replace(self, seat_id: str, new_occupant_id: str) -> dict[str, Any]:
        seat = self.seats[seat_id]
        predecessor = {
            "occupant_id": seat.occupant_id,
            "position": seat.position,
            "ballots": list(seat.ballots),
            "role_id": seat.role_id,
            "mandate": seat.mandate.as_dict(),
        }
        seat.occupant_id = new_occupant_id
        seat.position = None
        seat.ballots = []
        rec = {
            "seat_id": seat_id,
            "predecessor": predecessor,
            "replacement_occupant_id": new_occupant_id,
            "inherited_role_id": seat.role_id,
            "inherited_mandate": seat.mandate.as_dict(),
            "inherited_position": seat.position,
            "inherited_ballots": list(seat.ballots),
        }
        self.replacements.append(rec)
        self._emit(
            seat,
            "replace",
            True,
            "role-inherited-position-cleared",
            new_occupant_id,
        )
        return rec

    def participant_action_logs(self) -> list[dict[str, Any]]:
        by_occupant: dict[str, list[Event]] = {}
        order: list[tuple[str, str, str]] = []
        for ev in self.events:
            key = ev.occupant_id
            if key not in by_occupant:
                by_occupant[key] = []
                order.append((ev.occupant_id, ev.seat_id, ev.role_id))
            by_occupant[key].append(ev)
        logs = []
        for occupant_id, seat_id, role_id in order:
            logs.append(
                {
                    "occupant_id": occupant_id,
                    "seat_id": seat_id,
                    "role_id": role_id,
                    "events": [e.as_dict() for e in by_occupant[occupant_id]],
                }
            )
        return logs

    def fingerprint(self) -> str:
        parts = [
            f"{e.occupant_id}:{e.action}:{int(e.accepted)}"
            for e in self.events
            if e.action in {"speak", "vote", "veto"}
        ]
        return "|".join(parts)

    def accepted_counts(self) -> dict[str, int]:
        out = {"speak": 0, "vote": 0, "veto": 0}
        for e in self.events:
            if e.accepted and e.action in out:
                out[e.action] += 1
        return out
