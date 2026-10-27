"""Adversarial (proposer/refuter) seat selection with a measurable spread metric.

The refuter for each proposer is the candidate at MAXIMUM position distance —
labels are ignored, so a participant merely LABELED "refuter" whose position
agrees with the proposers (the label trap) is never seated. First-round spread
is measured from the emitted transcripts themselves: polarity is the dot
product of an extracted POSITION vector with the question axis, and the spread
is the mean pairwise absolute polarity difference.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from typing import Any

#: Minimum extracted-position distance for a refuter to count as opposed.
AGREE_DISTANCE = 1.0

_POSITION_RE = re.compile(r"^POSITION\s+(\[[^\n]+\])\s*$", re.MULTILINE)

Vec = tuple[float, float, float]


def euclidean(a, b) -> float:
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


@dataclass(frozen=True)
class Participant:
    participant_id: str
    position: Vec
    label: str = "panelist"


@dataclass(frozen=True)
class Question:
    question_id: str
    prompt: str
    axis: Vec


@dataclass
class Seat:
    seat_id: str
    role: str
    participant: Participant
    pair_index: int = -1


@dataclass
class Finding:
    code: str
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "detail": self.detail}


@dataclass
class Selection:
    seats: list[Seat] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    def pairs(self) -> list[tuple[Seat, Seat]]:
        by_pair: dict[int, dict[str, Seat]] = {}
        for seat in self.seats:
            if seat.pair_index >= 0:
                by_pair.setdefault(seat.pair_index, {})[seat.role] = seat
        out: list[tuple[Seat, Seat]] = []
        for idx in sorted(by_pair):
            duo = by_pair[idx]
            if "proposer" in duo and "refuter" in duo:
                out.append((duo["proposer"], duo["refuter"]))
        return out


@dataclass
class Turn:
    seat_id: str
    participant_id: str
    role: str
    text: str
    extracted_position: Vec


def default_pool() -> list[Participant]:
    """Proposer cluster first (sequential/unpaired picks land here), then the
    label trap and mid-ground fillers, then the genuinely opposed cluster."""
    return [
        Participant("P-pro-1", (1.0, 0.8, 0.6), label="proposer"),
        Participant("P-pro-2", (0.9, 1.0, 0.7), label="proposer"),
        Participant("P-pro-3", (0.8, 0.7, 1.0), label="proposer"),
        Participant("R-label-only", (0.95, 0.85, 0.65), label="refuter"),
        Participant("N-mid-1", (0.2, 0.1, 0.15), label="panelist"),
        Participant("N-mid-2", (0.1, 0.2, 0.05), label="panelist"),
        Participant("R-neg-1", (-1.0, -0.8, -0.6), label="refuter"),
        Participant("R-neg-2", (-0.9, -1.0, -0.7), label="refuter"),
        Participant("C-neg-3", (-0.8, -0.7, -1.0), label="contrarian"),
    ]


def default_questions() -> list[Question]:
    axes: list[Vec] = [
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
        (0.5, 0.5, 0.0),
        (0.5, 0.0, 0.5),
        (0.0, 0.5, 0.5),
        (0.4, 0.4, 0.2),
        (0.2, 0.4, 0.4),
        (0.4, 0.2, 0.4),
        (0.34, 0.33, 0.33),
    ]
    return [
        Question(f"Q-{i + 1:02d}", f"Matched question {i + 1}", axis)
        for i, axis in enumerate(axes)
    ]


def select_adversarial(pool: list[Participant], n_proposers: int = 3) -> Selection:
    """Pair each proposer with the maximally position-opposed remaining candidate."""
    sel = Selection()
    proposers = pool[:n_proposers]
    candidates = list(pool[n_proposers:])
    for idx, prop in enumerate(proposers):
        sel.seats.append(Seat(f"seat-{idx}-proposer", "proposer", prop, pair_index=idx))
        if not candidates:
            sel.findings.append(Finding("no-opposed-candidate", f"pool exhausted for {prop.participant_id}"))
            continue
        best = max(candidates, key=lambda c: euclidean(prop.position, c.position))
        gap = euclidean(prop.position, best.position)
        if gap < AGREE_DISTANCE:
            sel.findings.append(
                Finding(
                    "no-opposed-candidate",
                    f"best candidate {best.participant_id} gap {gap:.3f} < {AGREE_DISTANCE}",
                )
            )
        candidates.remove(best)
        sel.seats.append(Seat(f"seat-{idx}-refuter", "refuter", best, pair_index=idx))
    return sel


def select_unpaired(pool: list[Participant], n_seats: int, mode: str = "sequential") -> Selection:
    if mode != "sequential":
        raise ValueError(f"unknown mode {mode!r}")
    sel = Selection()
    for idx, part in enumerate(pool[:n_seats]):
        sel.seats.append(Seat(f"useat-{idx}", "panelist", part, pair_index=-1))
    return sel


def _position_line(vec) -> str:
    return "POSITION " + json.dumps([float(v) for v in vec])


def parse_position(text: str) -> Vec:
    m = _POSITION_RE.search(text)
    if not m:
        raise ValueError("POSITION line missing")
    vec = json.loads(m.group(1))
    return (float(vec[0]), float(vec[1]), float(vec[2]))


def emit_first_round(selection: Selection, question: Question, agree_mode: str = "none") -> list[Turn]:
    """Emit one transcript turn per seat. ``agree_mode`` plants the defect:

    * ``none`` — genuine opposition (refuter argues and positions against)
    * ``full`` — refuter copies the proposer's position AND agrees in prose
    * ``position-only`` — refuter still SAYS "I refute" but copies the position
    """
    if agree_mode not in {"none", "full", "position-only"}:
        raise ValueError(f"unknown agree_mode {agree_mode!r}")
    proposer_by_pair = {
        s.pair_index: s for s in selection.seats if s.role == "proposer" and s.pair_index >= 0
    }
    turns: list[Turn] = []
    for seat in selection.seats:
        pid = seat.participant.participant_id
        if seat.role == "refuter":
            proposer = proposer_by_pair.get(seat.pair_index)
            if agree_mode == "full" and proposer is not None:
                pos = proposer.participant.position
                prose = (
                    f"I agree with the proposer on {question.question_id}; "
                    "their plan already holds."
                )
            elif agree_mode == "position-only" and proposer is not None:
                pos = proposer.participant.position
                prose = (
                    f"I refute the proposer's claim on {question.question_id}: "
                    "COUNTER the plan fails under load."
                )
            else:
                pos = seat.participant.position
                prose = (
                    f"I refute the proposer's claim on {question.question_id}: "
                    "COUNTER the plan fails under load."
                )
            text = (
                f"CLAIM counter for {question.question_id} by {pid}.\n"
                f"{_position_line(pos)}\n"
                f"{prose}\n"
            )
        elif seat.role == "proposer":
            pos = seat.participant.position
            text = (
                f"CLAIM proposal for {question.question_id} by {pid}: adopt the measured plan.\n"
                f"{_position_line(pos)}\n"
                "I propose the measured plan; the evidence supports it.\n"
            )
        else:
            pos = seat.participant.position
            text = (
                f"CLAIM statement for {question.question_id} by {pid}.\n"
                f"{_position_line(pos)}\n"
                "I state my independent reading of the question.\n"
            )
        turns.append(
            Turn(
                seat_id=seat.seat_id,
                participant_id=pid,
                role=seat.role,
                text=text,
                extracted_position=parse_position(text),
            )
        )
    return turns


def polarity(text_or_vec, axis) -> float:
    vec = parse_position(text_or_vec) if isinstance(text_or_vec, str) else text_or_vec
    return sum(float(a) * float(b) for a, b in zip(vec, axis))


def polarity_spread(texts: list[str], axis) -> float:
    """Mean pairwise absolute polarity difference over emitted texts."""
    xs = [polarity(t, axis) for t in texts]
    n = len(xs)
    if n < 2:
        return 0.0
    acc = 0.0
    k = 0
    for i in range(n):
        for j in range(i + 1, n):
            acc += abs(xs[i] - xs[j])
            k += 1
    return acc / k


def run_matched_experiment(
    pool: list[Participant], questions: list[Question], n_proposers: int = 3
) -> dict[str, Any]:
    """Paired vs sequential-unpaired first-round spread on matched questions.

    Spreads are recomputed FROM THE EMITTED TEXTS (the same signal an
    independent recount parses), not from private state.
    """
    paired = select_adversarial(pool, n_proposers=n_proposers)
    unpaired = select_unpaired(pool, n_seats=len(paired.seats), mode="sequential")
    rows: list[dict[str, Any]] = []
    transcripts: list[dict[str, Any]] = []
    for q in questions:
        p_turns = emit_first_round(paired, q, agree_mode="none")
        u_turns = emit_first_round(unpaired, q, agree_mode="none")
        p_spread = polarity_spread([t.text for t in p_turns], q.axis)
        u_spread = polarity_spread([t.text for t in u_turns], q.axis)
        rows.append(
            {
                "question_id": q.question_id,
                "paired_spread": p_spread,
                "unpaired_spread": u_spread,
                "paired_gt_unpaired": p_spread > u_spread,
            }
        )
        by_seat = {t.seat_id: t for t in p_turns}
        transcripts.append(
            {
                "question_id": q.question_id,
                "pairs": [
                    {
                        "proposer_id": prop.participant.participant_id,
                        "refuter_id": ref.participant.participant_id,
                        "proposer_text": by_seat[prop.seat_id].text,
                        "refuter_text": by_seat[ref.seat_id].text,
                    }
                    for prop, ref in paired.pairs()
                ],
            }
        )
    return {"rows": rows, "transcripts": transcripts}


def structured_opposition_read(proposer_text: str, refuter_text: str) -> dict[str, Any]:
    """Independent structured read: does the refuter actually oppose?"""
    p_pos = parse_position(proposer_text)
    r_pos = parse_position(refuter_text)
    gap = euclidean(p_pos, r_pos)
    p_claim = next((ln for ln in proposer_text.splitlines() if ln.startswith("CLAIM")), "")
    r_counter = next((ln for ln in refuter_text.splitlines() if "I refute" in ln or "COUNTER" in ln), "")
    opposed = (
        "I refute" in refuter_text
        and "I agree with the proposer" not in refuter_text
        and gap >= AGREE_DISTANCE
    )
    return {
        "opposed": opposed,
        "gap": gap,
        "proposer_claim": p_claim,
        "refuter_counter": r_counter,
    }


def flag_agreeing_refuters(turns: list[Turn], selection: Selection) -> list[dict[str, Any]]:
    """FIRE when a refuter's extracted position sits inside AGREE_DISTANCE of
    its proposer — prose is not consulted, so 'I refute' cannot mask agreement."""
    by_seat = {t.seat_id: t for t in turns}
    flags: list[dict[str, Any]] = []
    for prop, ref in selection.pairs():
        p_turn = by_seat.get(prop.seat_id)
        r_turn = by_seat.get(ref.seat_id)
        if p_turn is None or r_turn is None:
            continue
        gap = euclidean(p_turn.extracted_position, r_turn.extracted_position)
        if gap < AGREE_DISTANCE:
            flags.append(
                {
                    "code": "agreeing-refuter",
                    "proposer": prop.participant.participant_id,
                    "refuter": ref.participant.participant_id,
                    "gap": gap,
                    "threshold": AGREE_DISTANCE,
                }
            )
    return flags


def clone_pool_no_opposition(pool: list[Participant]) -> list[Participant]:
    """Every non-proposer position becomes a near-clone of the proposer cluster."""
    out: list[Participant] = []
    for idx, part in enumerate(pool):
        if idx < 3:
            out.append(part)
        else:
            base = pool[idx % 3].position
            jitter = 0.01 * (idx + 1)
            pos = (base[0] - jitter, base[1] - jitter, base[2] - jitter)
            out.append(Participant(part.participant_id, pos, label=part.label))
    return out


def agreeing_refuter_control(
    pool: list[Participant], question: Question, n_proposers: int = 3
) -> dict[str, Any]:
    """Both-states control: SILENT on genuine opposition, FIRE on agreement."""
    sel = select_adversarial(pool, n_proposers=n_proposers)
    genuine = flag_agreeing_refuters(emit_first_round(sel, question, agree_mode="none"), sel)
    full = flag_agreeing_refuters(emit_first_round(sel, question, agree_mode="full"), sel)
    pos_only = flag_agreeing_refuters(
        emit_first_round(sel, question, agree_mode="position-only"), sel
    )
    n_pairs = len(sel.pairs())
    silent = len(genuine) == 0
    fires = len(full) == n_pairs and len(pos_only) == n_pairs
    return {
        "pass": bool(silent and fires and n_pairs == n_proposers),
        "silent_on_good": silent,
        "fire_on_full": len(full),
        "fire_on_position_only": len(pos_only),
        "n_pairs": n_pairs,
    }


__all__ = [
    "AGREE_DISTANCE",
    "Finding",
    "Participant",
    "Question",
    "Seat",
    "Selection",
    "Turn",
    "agreeing_refuter_control",
    "clone_pool_no_opposition",
    "default_pool",
    "default_questions",
    "emit_first_round",
    "euclidean",
    "flag_agreeing_refuters",
    "parse_position",
    "polarity",
    "polarity_spread",
    "run_matched_experiment",
    "select_adversarial",
    "select_unpaired",
    "structured_opposition_read",
]
