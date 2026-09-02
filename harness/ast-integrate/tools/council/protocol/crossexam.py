"""Cross-examination pairing schedule (IMP-0363)."""
from __future__ import annotations

from dataclasses import dataclass, field
from math import floor
from typing import Any

DEPTH_BOUND = 2
SELF_EXAM = "self-exam"


@dataclass
class Position:
    position_id: str
    holder: str = ""
    popularity: float = 0.0
    substantive: bool = True
    text: str = ""

    @property
    def author_id(self) -> str:
        return self.holder


@dataclass
class Pairing:
    position_id: str
    examiner: str
    depth: int
    kind: str = "cross"

    @property
    def examiner_id(self) -> str:
        return self.examiner


@dataclass
class Correlation:
    sign: str = "positive"
    r: float = 0.8


@dataclass
class Schedule:
    pairings: list[Pairing] = field(default_factory=list)
    complete: bool = True
    correlation: Correlation = field(default_factory=Correlation)


def examination_quota(popularity: float, max_popularity: float, max_depth: int) -> int:
    if max_popularity <= 0:
        return 1
    return 1 + floor((max_depth - 1) * float(popularity) / float(max_popularity))


def pairing_is_valid_exam(pos: Position, pairing: Pairing) -> bool:
    if not pos.substantive:
        return False
    if pairing.kind == SELF_EXAM:
        return False
    return pairing.examiner != pos.holder and pairing.depth >= 1


def schedule_cross_examination(
    positions: list[Position],
    participants: tuple[str, ...] | list[str],
    max_depth: int = DEPTH_BOUND,
) -> Schedule:
    subst = [p for p in positions if p.substantive]
    max_pop = max((p.popularity for p in subst), default=1.0) or 1.0
    pairings: list[Pairing] = []
    seats = [s for s in participants if s]
    for pos in subst:
        quota = examination_quota(pos.popularity, max_pop, max_depth)
        examiners = [s for s in seats if s != pos.holder]
        for i in range(quota):
            examiner = examiners[i % len(examiners)] if examiners else pos.holder
            depth = 1 if quota == 1 else (1 if i == 0 else min(max_depth, 2))
            kind = SELF_EXAM if examiner == pos.holder else "cross"
            pairings.append(
                Pairing(position_id=pos.position_id, examiner=examiner, depth=depth, kind=kind)
            )
    return Schedule(pairings=pairings)


def propose_followup(position: Position, depth: int) -> Pairing:
    return Pairing(position_id=position.position_id, examiner="followup", depth=depth)


def audit_record(schedule: Schedule) -> dict[str, Any]:
    return {
        "n_pairings": len(schedule.pairings),
        "max_depth": max((p.depth for p in schedule.pairings), default=0),
    }
