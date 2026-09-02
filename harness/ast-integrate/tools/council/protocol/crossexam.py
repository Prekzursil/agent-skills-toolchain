"""Cross-examination pairing schedule with bounded depth (IMP-0363).

Who examines whose position, how many times, and how deep the follow-ups may
go.  Every *substantive* position gets an examination quota that grows with
its popularity (:func:`examination_quota` - ``1 + floor((max_depth - 1) *
popularity / max_popularity)``), so the dominant position draws the most
scrutiny rather than the least.  The first examination of a position is at
depth 1; each further examination is a follow-up chained on the previous
pairing (``parent_pairing_id``) one level deeper, never past ``max_depth``.
An author never examines their own position (``SELF_EXAM``) and a self-exam
pairing does not count as coverage.

The falsifiable question is whether the schedule tracks popularity or inverts
it: :func:`popularity_examination_correlation` publishes the Pearson *r* (with
its sign) between popularity and realised examination count over the
substantive rows, and :class:`Bias` says whether the dominant position was
left unchallenged while weaker ones were examined.  :func:`weak_only_schedule`
is the adversarial mutant that does exactly that; :func:`drop_position_pairings`
plants an unexamined position so the coverage gap must be reported
(``Schedule.gaps``, ``Schedule.complete``).  Procedural, non-substantive
positions are never scheduled and are never gaps.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from math import floor
from typing import Any, Iterable, Sequence

__all__ = [
    "DEFAULT_MAX_DEPTH",
    "DEPTH_BOUND",
    "SELF_EXAM",
    "UNKNOWN_PARENT",
    "UNKNOWN_EXAMINER",
    "UNKNOWN_POSITION",
    "DUPLICATE_EXAMINER",
    "NOT_SUBSTANTIVE",
    "KIND_CROSS",
    "KIND_FOLLOWUP",
    "Position",
    "Pairing",
    "CoverageRow",
    "Correlation",
    "Bias",
    "Schedule",
    "Proposal",
    "examination_quota",
    "pairing_is_valid_exam",
    "coverage_matrix",
    "coverage_gaps",
    "popularity_examination_correlation",
    "bias_report",
    "audit_record",
    "schedule_cross_examination",
    "propose_followup",
    "drop_position_pairings",
    "weak_only_schedule",
]

DEFAULT_MAX_DEPTH = 2
# Refusal reason codes (``Proposal.reason`` / ``Schedule.violations``).
DEPTH_BOUND = "depth-bound"
SELF_EXAM = "self-exam"
UNKNOWN_PARENT = "unknown-parent"
UNKNOWN_EXAMINER = "unknown-examiner"
UNKNOWN_POSITION = "unknown-position"
DUPLICATE_EXAMINER = "duplicate-examiner"
NOT_SUBSTANTIVE = "not-substantive"
KIND_CROSS = "cross"
KIND_FOLLOWUP = "followup"


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
    """One examination: ``examiner_id`` examines ``position_id`` at ``depth``."""

    pairing_id: str = ""
    examiner_id: str = ""
    position_id: str = ""
    depth: int = 1
    parent_pairing_id: str | None = None
    kind: str = KIND_CROSS

    def __post_init__(self) -> None:
        self.depth = int(self.depth)
        if not self.pairing_id:
            self.pairing_id = f"X-{self.position_id}-{self.examiner_id}-d{self.depth}"
        if self.parent_pairing_id is not None and self.kind == KIND_CROSS:
            self.kind = KIND_FOLLOWUP

    @property
    def examiner(self) -> str:
        return self.examiner_id

    def as_dict(self) -> dict[str, Any]:
        return {
            "pairing_id": self.pairing_id,
            "examiner_id": self.examiner_id,
            "position_id": self.position_id,
            "depth": self.depth,
            "parent_pairing_id": self.parent_pairing_id,
            "kind": self.kind,
        }


@dataclass
class CoverageRow:
    position_id: str
    author_id: str
    popularity: float
    substantive: bool
    examination_count: int
    examiner_ids: list[str]
    depths: list[int]
    gap: bool


@dataclass(frozen=True)
class Correlation:
    coefficient: float | None
    n: int
    sign: str
    undefined_reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "coefficient": self.coefficient,
            "n": self.n,
            "sign": self.sign,
            "undefined_reason": self.undefined_reason,
        }


@dataclass(frozen=True)
class Bias:
    dominant_position_id: str | None
    dominant_popularity: float | None
    dominant_examination_count: int
    dominant_examined: bool
    favours_weak_leaves_dominant_unchallenged: bool
    correlation: Correlation

    def as_dict(self) -> dict[str, Any]:
        return {
            "dominant_position_id": self.dominant_position_id,
            "dominant_popularity": self.dominant_popularity,
            "dominant_examination_count": self.dominant_examination_count,
            "dominant_examined": self.dominant_examined,
            "favours_weak_leaves_dominant_unchallenged": (
                self.favours_weak_leaves_dominant_unchallenged
            ),
            "correlation": self.correlation.as_dict(),
        }


@dataclass
class Schedule:
    """Pairings plus the audit computed from them."""

    positions: tuple[Position, ...] = ()
    participants: tuple[str, ...] = ()
    max_depth: int = DEFAULT_MAX_DEPTH
    pairings: tuple[Pairing, ...] = ()
    coverage: tuple[CoverageRow, ...] = ()
    gaps: tuple[str, ...] = ()
    complete: bool = False
    correlation: Correlation = field(
        default_factory=lambda: Correlation(None, 0, "undefined", "empty")
    )
    bias: Bias = field(
        default_factory=lambda: Bias(None, None, 0, False, False, Correlation(None, 0, "undefined", "empty"))
    )
    violations: tuple[str, ...] = ()

    def pairing(self, pairing_id: str) -> Pairing | None:
        for p in self.pairings:
            if p.pairing_id == pairing_id:
                return p
        return None

    def as_dict(self) -> dict[str, Any]:
        return {
            "participants": list(self.participants),
            "max_depth": self.max_depth,
            "pairings": [p.as_dict() for p in self.pairings],
            "coverage": [row.__dict__ for row in self.coverage],
            "gaps": list(self.gaps),
            "complete": self.complete,
            "correlation": self.correlation.as_dict(),
            "bias": self.bias.as_dict(),
            "violations": list(self.violations),
            "n_pairings": len(self.pairings),
        }


@dataclass(frozen=True)
class Proposal:
    accepted: bool
    reason: str | None
    pairing: Pairing | None = None
    schedule: Schedule | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "reason": self.reason,
            "pairing": self.pairing.as_dict() if self.pairing else None,
        }


# ------------------------------------------------------------------------- quotas
def examination_quota(popularity: float, max_popularity: float, max_depth: int) -> int:
    """Examinations owed to a position: more popular, more scrutiny.

    ``1 + floor((max_depth - 1) * popularity / max_popularity)``; monotone in
    popularity, at least 1, at most ``max_depth``.
    """
    depth = max(1, int(max_depth))
    if max_popularity <= 0:
        return 1
    share = max(0.0, float(popularity)) / float(max_popularity)
    return min(depth, 1 + floor((depth - 1) * share))


def pairing_is_valid_exam(pos: Position, pairing: Pairing) -> bool:
    """A pairing covers ``pos`` only if it targets it, is not a self-exam and
    sits at depth >= 1."""
    if not pos.substantive:
        return False
    if pairing.position_id != pos.position_id:
        return False
    if pairing.kind == SELF_EXAM or pairing.examiner_id == pos.author_id:
        return False
    return int(pairing.depth) >= 1


# ----------------------------------------------------------------------- coverage
def coverage_matrix(positions: Sequence[Position], pairings: Iterable[Pairing]) -> list[CoverageRow]:
    """One row per position (input order) counting its *valid* examinations."""
    rows: list[CoverageRow] = []
    pairings = list(pairings)
    for pos in positions:
        valid = [p for p in pairings if pairing_is_valid_exam(pos, p)]
        count = len(valid)
        rows.append(
            CoverageRow(
                position_id=pos.position_id,
                author_id=pos.author_id,
                popularity=float(pos.popularity),
                substantive=bool(pos.substantive),
                examination_count=count,
                examiner_ids=[p.examiner_id for p in valid],
                depths=[int(p.depth) for p in valid],
                gap=bool(pos.substantive) and count == 0,
            )
        )
    return rows


def coverage_gaps(coverage: Iterable[CoverageRow]) -> list[str]:
    """Substantive positions with no valid examination, in matrix order."""
    gaps: list[str] = []
    for row in coverage:
        if row.substantive and row.examination_count == 0 and row.gap:
            gaps.append(row.position_id)
    return gaps


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> Correlation:
    n = len(xs)
    if n < 2 or n != len(ys):
        return Correlation(None, n, "undefined", "n")
    mx = sum(xs) / n
    my = sum(ys) / n
    num = varx = vary = 0.0
    for x, y in zip(xs, ys):
        num += (x - mx) * (y - my)
        varx += (x - mx) ** 2
        vary += (y - my) ** 2
    if varx == 0.0 or vary == 0.0:
        return Correlation(None, n, "undefined", "zero-variance")
    r = num / math.sqrt(varx * vary)
    sign = "positive" if r > 0 else "negative" if r < 0 else "zero"
    return Correlation(r, n, sign, None)


def popularity_examination_correlation(coverage: Iterable[CoverageRow]) -> Correlation:
    """Pearson r between popularity and examination count over substantive rows."""
    rows = [row for row in coverage if row.substantive]
    return _pearson([row.popularity for row in rows], [float(row.examination_count) for row in rows])


def bias_report(coverage: Sequence[CoverageRow]) -> Bias:
    """Was the most popular position left unchallenged while weaker ones were examined?"""
    correlation = popularity_examination_correlation(coverage)
    substantive = [row for row in coverage if row.substantive]
    if not substantive:
        return Bias(None, None, 0, False, False, correlation)
    dominant = max(substantive, key=lambda row: (row.popularity, -substantive.index(row)))
    others_examined = any(
        row.examination_count > 0 for row in substantive if row.position_id != dominant.position_id
    )
    examined = dominant.examination_count > 0
    return Bias(
        dominant_position_id=dominant.position_id,
        dominant_popularity=dominant.popularity,
        dominant_examination_count=dominant.examination_count,
        dominant_examined=examined,
        favours_weak_leaves_dominant_unchallenged=(not examined) and others_examined,
        correlation=correlation,
    )


def _violations(
    positions: Sequence[Position],
    pairings: Sequence[Pairing],
    max_depth: int,
    participant_ids: Sequence[str] | None,
) -> list[str]:
    by_id = {p.position_id: p for p in positions}
    seats = set(participant_ids) if participant_ids is not None else None
    out: list[str] = []
    for p in pairings:
        pos = by_id.get(p.position_id)
        if pos is None:
            out.append(f"{UNKNOWN_POSITION}:{p.pairing_id}")
            continue
        if not pos.substantive:
            out.append(f"{NOT_SUBSTANTIVE}:{p.pairing_id}")
        if seats is not None and p.examiner_id not in seats:
            out.append(f"{UNKNOWN_EXAMINER}:{p.pairing_id}")
        if p.examiner_id == pos.author_id or p.kind == SELF_EXAM:
            out.append(f"{SELF_EXAM}:{p.pairing_id}")
        if int(p.depth) < 1 or int(p.depth) > int(max_depth):
            out.append(f"{DEPTH_BOUND}:{p.pairing_id}")
    return out


def audit_record(
    positions: Sequence[Position],
    pairings: Sequence[Pairing] | None = None,
    max_depth: int = DEFAULT_MAX_DEPTH,
    participant_ids: Sequence[str] | None = None,
) -> Schedule:
    """Audit an arbitrary pairing list: coverage, gaps, correlation, bias, violations.

    Called with a :class:`Schedule` alone it re-audits that schedule.
    """
    if isinstance(positions, Schedule) and pairings is None:
        sched = positions
        return audit_record(sched.positions, sched.pairings, sched.max_depth, sched.participants)
    positions = tuple(positions)
    pairings = tuple(pairings or ())
    if participant_ids is None:
        seen: list[str] = []
        for pos in positions:
            if pos.author_id and pos.author_id not in seen:
                seen.append(pos.author_id)
        for p in pairings:
            if p.examiner_id and p.examiner_id not in seen:
                seen.append(p.examiner_id)
        participant_ids = seen
    coverage = tuple(coverage_matrix(positions, pairings))
    gaps = tuple(coverage_gaps(coverage))
    substantive = [row for row in coverage if row.substantive]
    return Schedule(
        positions=positions,
        participants=tuple(str(s) for s in participant_ids),
        max_depth=int(max_depth),
        pairings=pairings,
        coverage=coverage,
        gaps=gaps,
        complete=not gaps and all(row.examination_count >= 1 for row in substantive),
        correlation=popularity_examination_correlation(coverage),
        bias=bias_report(coverage),
        violations=tuple(_violations(positions, pairings, max_depth, participant_ids)),
    )


# ---------------------------------------------------------------------- scheduling
def _examiners_for(pos: Position, participants: Sequence[str]) -> list[str]:
    return [s for s in participants if s and s != pos.author_id]


def _chain(pos: Position, examiners: Sequence[str], quota: int, counter: list[int]) -> list[Pairing]:
    out: list[Pairing] = []
    parent: Pairing | None = None
    for depth, examiner in enumerate(examiners[:quota], 1):
        counter[0] += 1
        pairing = Pairing(
            pairing_id=f"X-{counter[0]:03d}",
            examiner_id=examiner,
            position_id=pos.position_id,
            depth=depth,
            parent_pairing_id=parent.pairing_id if parent else None,
            kind=KIND_CROSS if parent is None else KIND_FOLLOWUP,
        )
        out.append(pairing)
        parent = pairing
    return out


def schedule_cross_examination(
    positions: Sequence[Position],
    participants: Sequence[str],
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> Schedule:
    """Pair every substantive position with popularity-proportional examiners.

    Position *i* is examined by the first ``quota`` participants who are not
    its author, the first at depth 1 and each further one as a follow-up one
    level deeper; ``max_depth`` bounds both the quota and the chain.
    """
    seats = [str(s) for s in participants if str(s)]
    depth = max(1, int(max_depth))
    substantive = [p for p in positions if p.substantive]
    max_pop = max((float(p.popularity) for p in substantive), default=0.0)
    counter = [0]
    pairings: list[Pairing] = []
    for pos in substantive:
        quota = examination_quota(pos.popularity, max_pop, depth)
        pairings.extend(_chain(pos, _examiners_for(pos, seats), quota, counter))
    return audit_record(positions, pairings, depth, seats)


def propose_followup(
    positions: Sequence[Position],
    schedule: Schedule,
    parent_pairing_id: str,
    examiner_id: str,
) -> Proposal:
    """Chain a follow-up examination on ``parent_pairing_id``.

    Refused with ``DEPTH_BOUND`` when the child would exceed the schedule's
    ``max_depth``, ``SELF_EXAM`` when the examiner authored the position,
    ``UNKNOWN_PARENT`` / ``UNKNOWN_EXAMINER`` / ``DUPLICATE_EXAMINER`` otherwise.
    Accepted proposals return the re-audited schedule.
    """
    parent = schedule.pairing(parent_pairing_id)
    if parent is None:
        return Proposal(False, UNKNOWN_PARENT)
    by_id = {p.position_id: p for p in positions}
    pos = by_id.get(parent.position_id)
    if pos is None:
        return Proposal(False, UNKNOWN_POSITION)
    if schedule.participants and examiner_id not in schedule.participants:
        return Proposal(False, UNKNOWN_EXAMINER)
    depth = int(parent.depth) + 1
    if depth > int(schedule.max_depth):
        return Proposal(False, DEPTH_BOUND)
    if examiner_id == pos.author_id:
        return Proposal(False, SELF_EXAM)
    if any(p.position_id == pos.position_id and p.examiner_id == examiner_id for p in schedule.pairings):
        return Proposal(False, DUPLICATE_EXAMINER)
    pairing = Pairing(
        pairing_id=f"X-{len(schedule.pairings) + 1:03d}",
        examiner_id=examiner_id,
        position_id=pos.position_id,
        depth=depth,
        parent_pairing_id=parent.pairing_id,
        kind=KIND_FOLLOWUP,
    )
    new = audit_record(
        positions, tuple(schedule.pairings) + (pairing,), schedule.max_depth, schedule.participants
    )
    return Proposal(True, None, pairing, new)


# ------------------------------------------------------------------------ mutants
def drop_position_pairings(positions: Sequence[Position], schedule: Schedule, position_id: str) -> Schedule:
    """Plant a coverage gap: remove every pairing that examines ``position_id``."""
    kept = tuple(p for p in schedule.pairings if p.position_id != position_id)
    return audit_record(positions, kept, schedule.max_depth, schedule.participants)


def weak_only_schedule(
    positions: Sequence[Position],
    participants: Sequence[str],
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> Schedule:
    """Adversarial mutant: examine the weak positions, skip the dominant half.

    Positions at or above half the maximum popularity are left unchallenged;
    the rest receive a quota that grows as popularity *falls*.  The audit of
    this schedule must report the dominant position as a gap, a negative
    popularity/examination correlation and ``favours_weak_leaves_dominant_unchallenged``.
    """
    seats = [str(s) for s in participants if str(s)]
    depth = max(1, int(max_depth))
    substantive = [p for p in positions if p.substantive]
    max_pop = max((float(p.popularity) for p in substantive), default=0.0)
    counter = [0]
    pairings: list[Pairing] = []
    for pos in substantive:
        if max_pop > 0 and float(pos.popularity) >= max_pop / 2:
            continue
        quota = examination_quota(max_pop - float(pos.popularity), max_pop, depth)
        pairings.extend(_chain(pos, _examiners_for(pos, seats), quota, counter))
    return audit_record(positions, pairings, depth, seats)
