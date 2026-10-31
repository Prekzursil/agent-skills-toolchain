"""Explicit roster seating with unavailability refusal and auto-substitution."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

HERE = Path(__file__).resolve().parent


@dataclass
class Seat:
    participant_id: str
    role: str
    substituted: bool = False
    available: bool = True


@dataclass
class Substitution:
    requested_id: str
    seated_id: str
    role: str


@dataclass
class RosterResult:
    ok: bool
    requested: list[str]
    seated: list[Seat] = field(default_factory=list)
    substitutions: list[Substitution] = field(default_factory=list)
    refusals: list[dict[str, Any]] = field(default_factory=list)
    auto_substitution: bool = False

    def seated_ids(self) -> list[str]:
        return [s.participant_id for s in self.seated]

    def set_equals(self) -> bool:
        return set(self.requested) == set(self.seated_ids())

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "requested": list(self.requested),
            "seated": self.seated_ids(),
            "substitutions": [
                {"requested_id": s.requested_id, "seated_id": s.seated_id}
                for s in self.substitutions
            ],
            "refusals": list(self.refusals),
            "auto_substitution": self.auto_substitution,
        }


def fixture_dir() -> Path:
    return HERE / "fixtures"


def _as_seat(item: Any) -> Seat:
    if isinstance(item, Seat):
        return item
    if isinstance(item, Mapping):
        return Seat(
            participant_id=str(item.get("participant_id") or item.get("id") or ""),
            role=str(item.get("role") or ""),
            available=item.get("available", True) is not False,
        )
    return Seat(participant_id=str(item), role="")


def _lookup_row(lookup: Mapping[str, Any], pid: str) -> dict[str, Any]:
    row = lookup.get(pid) or {}
    if isinstance(row, Mapping):
        return dict(row)
    return {"available": True}


def load_roster_fixture(path: Path) -> tuple[dict[str, Any], list[Seat]]:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    lookup = dict(doc.get("lookup") or {})
    seats = [_as_seat(s) for s in (doc.get("seats") or [])]
    for seat in seats:
        row = _lookup_row(lookup, seat.participant_id)
        if "role" in row and not seat.role:
            seat.role = str(row["role"])
        if "available" in row:
            seat.available = row["available"] is not False
    return lookup, seats


def roster_set_equals(requested: Iterable[Any], seated: Iterable[Any]) -> bool:
    def ids(items: Iterable[Any]) -> set[str]:
        out: set[str] = set()
        for item in items:
            if isinstance(item, Seat):
                out.add(item.participant_id)
            elif isinstance(item, Mapping):
                out.add(str(item.get("participant_id") or item.get("id") or ""))
            else:
                out.add(str(item))
        return out

    return ids(requested) == ids(seated)


def compare_rosters_as_set(requested: Sequence[Any], seated: Sequence[Any]) -> dict[str, Any]:
    def ids(items: Sequence[Any]) -> list[str]:
        out: list[str] = []
        for item in items:
            if isinstance(item, Seat):
                out.append(item.participant_id)
            elif isinstance(item, Mapping):
                out.append(str(item.get("participant_id") or item.get("id") or ""))
            else:
                out.append(str(item))
        return out

    req, got = ids(requested), ids(seated)
    missing = sorted(set(req) - set(got))
    extra = sorted(set(got) - set(req))
    return {"equal": not missing and not extra, "missing": missing, "extra": extra}


def resolve_explicit(seats: Sequence[Any], lookup: Mapping[str, Any]) -> RosterResult:
    requested = [_as_seat(s) for s in seats]
    requested_ids = [s.participant_id for s in requested]
    seated: list[Seat] = []
    refusals: list[dict[str, Any]] = []
    for seat in requested:
        row = _lookup_row(lookup, seat.participant_id)
        available = row.get("available", seat.available) is not False
        role = str(row.get("role") or seat.role)
        if not available:
            refusals.append(
                {
                    "kind": "participant-unavailable",
                    "participant_id": seat.participant_id,
                    "participant_named": True,
                    "substituted": False,
                    "reason": "unavailable",
                    "requested_roster": list(requested_ids),
                }
            )
            continue
        seated.append(Seat(participant_id=seat.participant_id, role=role, substituted=False))
    if refusals:
        return RosterResult(
            ok=False,
            requested=requested_ids,
            seated=[],
            refusals=refusals,
            auto_substitution=False,
        )
    return RosterResult(ok=True, requested=requested_ids, seated=seated, auto_substitution=False)


def resolve_with_auto_substitution(
    seats: Sequence[Any], lookup: Mapping[str, Any]
) -> RosterResult:
    requested = [_as_seat(s) for s in seats]
    requested_ids = [s.participant_id for s in requested]
    seated: list[Seat] = []
    substitutions: list[Substitution] = []
    # Candidates by role that are available and not already requested.
    by_role: dict[str, list[str]] = {}
    for pid, row in lookup.items():
        if not isinstance(row, Mapping):
            continue
        if row.get("available", True) is False:
            continue
        role = str(row.get("role") or "")
        by_role.setdefault(role, []).append(str(pid))
    taken = set(requested_ids)
    for seat in requested:
        row = _lookup_row(lookup, seat.participant_id)
        role = str(row.get("role") or seat.role)
        available = row.get("available", True) is not False
        if available:
            seated.append(Seat(participant_id=seat.participant_id, role=role, substituted=False))
            continue
        alt = next((pid for pid in by_role.get(role, []) if pid not in taken), None)
        if alt is None:
            return RosterResult(
                ok=False,
                requested=requested_ids,
                seated=[],
                auto_substitution=True,
                refusals=[
                    {
                        "kind": "participant-unavailable",
                        "participant_id": seat.participant_id,
                        "participant_named": True,
                        "substituted": False,
                        "reason": "unavailable",
                        "requested_roster": list(requested_ids),
                    }
                ],
            )
        taken.add(alt)
        seated.append(Seat(participant_id=alt, role=role, substituted=True))
        substitutions.append(Substitution(requested_id=seat.participant_id, seated_id=alt, role=role))
    return RosterResult(
        ok=True,
        requested=requested_ids,
        seated=seated,
        substitutions=substitutions,
        auto_substitution=True,
    )
