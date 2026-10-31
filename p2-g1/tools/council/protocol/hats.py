"""Six-Hats lens rotation (IMP-0334)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence

MODULE_REL = "tools/council/protocol/hats.py"
REASON_SINGLE_SEAT = "single-seat-cannot-wear-two-hats"
REASON_ROLE_COLLAPSE = "role-collapse"
ROLE_COLLAPSE_MAX_DISTANCE = 0
DEFAULT_QUESTION = "What should the council decide?"
DEFAULT_PARTICIPANTS = (
    {"id": "p-white", "name": "White"},
    {"id": "p-red", "name": "Red"},
    {"id": "p-black", "name": "Black"},
    {"id": "p-yellow", "name": "Yellow"},
    {"id": "p-green", "name": "Green"},
    {"id": "p-blue", "name": "Blue"},
)


@dataclass(frozen=True)
class Hat:
    lens_id: str
    color: str
    question: str


SIX_HATS: tuple[Hat, ...] = (
    Hat("white", "white", "What are the facts?"),
    Hat("red", "red", "What is the emotional read?"),
    Hat("black", "black", "What are the risks?"),
    Hat("yellow", "yellow", "What is the upside?"),
    Hat("green", "green", "What alternatives exist?"),
    Hat("blue", "blue", "How do we process the round?"),
)


def compile_schedule(
    participants: Sequence[Any] | None = None,
    question: str = DEFAULT_QUESTION,
) -> dict[str, Any]:
    roster = list(participants or DEFAULT_PARTICIPANTS)
    rounds = []
    for i, hat in enumerate(SIX_HATS):
        seat = roster[i % len(roster)]
        pid = seat["id"] if isinstance(seat, dict) else str(seat)
        rounds.append({"lens_id": hat.lens_id, "participant_id": pid, "question": hat.question})
    return {"question": question, "rounds": rounds, "complete": len(rounds) == 6}


def audit_schedule(schedule: dict[str, Any]) -> dict[str, Any]:
    lens_ids = [r.get("lens_id") for r in schedule.get("rounds") or []]
    missing = [h.lens_id for h in SIX_HATS if h.lens_id not in lens_ids]
    return {"ok": not missing, "missing": missing}


def plugin_record() -> dict[str, Any]:
    return {"module": MODULE_REL, "hats": [h.lens_id for h in SIX_HATS]}
