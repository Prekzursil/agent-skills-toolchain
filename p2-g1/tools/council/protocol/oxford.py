"""Oxford-style debate engine: proposition/opposition sides, timed turns and a
bounded rebuttal depth (IMP-0333).

The module exists to answer a falsifiable question mechanically: does the side
a participant is assigned change its stated conclusion more than the evidence
does?  The effect is PUBLISHED as a measured flip rate (side_swap_experiment /
evidence_swap_experiment / compare_side_vs_evidence), never asserted.  A high
side-swap flip rate everywhere would mean the protocol is measuring rhetoric,
not truth -- the negative control in tests and probe2 guards exactly that.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

PROPOSITION = "proposition"
OPPOSITION = "opposition"

# Published detector bounds (receipt measurements: low_flip_ceiling / high_flip_floor).
LOW_FLIP_CEILING = 0.25  # evidence-bound panel on a decisive motion must stay <= this
HIGH_FLIP_FLOOR = 0.75   # side-bound panel must score >= this, else detector is vacuous


@dataclass(frozen=True)
class DebateConfig:
    turn_budget_ms: int = 1000
    max_rebuttal_depth: int = 2


@dataclass(frozen=True)
class Motion:
    motion_id: str
    text: str
    evidence_for: tuple[str, ...]
    evidence_against: tuple[str, ...]
    decisive: bool = False

    def swap_evidence(self) -> "Motion":
        """Reverse evidence polarity, keep the motion text and id."""
        return replace(
            self,
            evidence_for=tuple(self.evidence_against),
            evidence_against=tuple(self.evidence_for),
        )


def decisive_arithmetic_motion() -> Motion:
    """Evidence-decisive motion: the evidence alone settles it (2+2=4)."""
    return Motion(
        motion_id="arith-2plus2",
        text="This house believes that 2 + 2 = 4.",
        evidence_for=(
            "Peano arithmetic: S(S(0)) + S(S(0)) = S(S(S(S(0)))) = 4, proved.",
        ),
        evidence_against=(),
        decisive=True,
    )


def balanced_taste_motion() -> Motion:
    """Balanced-taste motion: evidence split evenly, so evidence cannot settle it."""
    split = "Diners are split on the sweet-savoury combination; surveys disagree."
    return Motion(
        motion_id="taste-pineapple-pizza",
        text="This house believes pineapple belongs on pizza.",
        evidence_for=(split,),
        evidence_against=(split,),
        decisive=False,
    )


@dataclass(frozen=True)
class Turn:
    participant_id: str
    side: str
    kind: str  # opening | rebuttal | closing
    depth: int
    text: str
    conclusion: str
    elapsed_ms: int
    timed_out: bool = False


class EvidenceBoundSpeaker:
    """Concludes from the motion's evidence; the assigned side is argued, not believed."""

    def __init__(self, participant_id: str, elapsed_ms: int = 10) -> None:
        self.participant_id = str(participant_id)
        self.elapsed_ms = int(elapsed_ms)

    def conclude(self, motion: Motion, side: str) -> tuple[str, str]:
        if motion.decisive:
            if motion.evidence_for and not motion.evidence_against:
                conclusion = PROPOSITION
            else:
                conclusion = OPPOSITION
            text = f"Evidence settles it: {conclusion} (assigned side {side} noted, not followed)."
            return conclusion, text
        n_for, n_against = len(motion.evidence_for), len(motion.evidence_against)
        if n_for != n_against:
            conclusion = PROPOSITION if n_for > n_against else OPPOSITION
        else:
            # Balanced evidence: the stance is fixed by the tie-break, never by the chair.
            conclusion = PROPOSITION
        text = (
            f"Evidence weighs {conclusion} ({n_for} for vs {n_against} against); "
            f"assigned side {side} did not move the conclusion."
        )
        return conclusion, text


class SideBoundSpeaker:
    """Rhetoric-bound: concludes whatever side it was assigned, evidence notwithstanding."""

    def __init__(self, participant_id: str, elapsed_ms: int = 10) -> None:
        self.participant_id = str(participant_id)
        self.elapsed_ms = int(elapsed_ms)

    def conclude(self, motion: Motion, side: str) -> tuple[str, str]:
        stance = "true" if side == PROPOSITION else "false"
        return side, f"As {side}, I assert the motion is {stance}."


@dataclass
class TimingAudit:
    budget_ms: int
    overruns: list[str] = field(default_factory=list)

    @property
    def overrun_count(self) -> int:
        return len(self.overruns)


class LocalTurnLoop:
    """Executes one scheduled turn locally; flags timing overruns against the budget."""

    def execute(self, turn: Turn, budget_ms: int) -> Turn:
        return replace(turn, timed_out=turn.elapsed_ms > budget_ms)


@dataclass
class DebateRecord:
    motion: Motion
    config: DebateConfig
    turns: list[Turn] = field(default_factory=list)
    timing: TimingAudit | None = None
    assignments: dict[str, str] = field(default_factory=dict)

    @property
    def turns_recorded(self) -> int:
        return len(self.turns)

    @property
    def turns_executed(self) -> int:
        return sum(1 for t in self.turns if t.text)

    def conclusions(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for t in self.turns:
            out[t.participant_id] = t.conclusion
        return out

    def turn_kinds(self) -> set[str]:
        return {t.kind for t in self.turns}

    def sides(self) -> set[str]:
        return {t.side for t in self.turns}


class RebuttalResult:
    def __init__(
        self,
        refused: bool,
        refuse_reason: str = "",
        turn: Turn | None = None,
    ) -> None:
        self.refused = bool(refused)
        self.refuse_reason = refuse_reason
        self.turn = turn


class OxfordProtocol:
    """Runs a motion: both sides seated, turns timed, rebuttal depth bounded."""

    def __init__(self, config: DebateConfig, loop: LocalTurnLoop | None = None) -> None:
        self.config = config
        self.loop = loop if loop is not None else LocalTurnLoop()

    def _schedule(self) -> list[tuple[str, int]]:
        phases: list[tuple[str, int]] = [("opening", 0)]
        phases += [("rebuttal", d) for d in range(1, self.config.max_rebuttal_depth + 1)]
        phases.append(("closing", 0))
        return phases

    def run(
        self,
        motion: Motion,
        speakers: dict[str, Any],
        assignments: dict[str, str],
    ) -> DebateRecord:
        audit = TimingAudit(budget_ms=self.config.turn_budget_ms)
        record = DebateRecord(
            motion=motion,
            config=self.config,
            timing=audit,
            assignments=dict(assignments),
        )
        for kind, depth in self._schedule():
            for pid in sorted(speakers):
                side = assignments.get(pid, PROPOSITION)
                conclusion, text = speakers[pid].conclude(motion, side)
                turn = Turn(
                    participant_id=pid,
                    side=side,
                    kind=kind,
                    depth=depth,
                    text=text,
                    conclusion=conclusion,
                    elapsed_ms=int(getattr(speakers[pid], "elapsed_ms", 0)),
                )
                turn = self.loop.execute(turn, self.config.turn_budget_ms)
                if turn.timed_out:
                    audit.overruns.append(f"{pid}:{kind}:d{depth}")
                record.turns.append(turn)
        return record

    def submit_rebuttal(
        self,
        record: DebateRecord,
        speakers: dict[str, Any],
        participant_id: str,
        depth: int,
    ) -> RebuttalResult:
        """Over-depth rebuttals are refused with the recorded reason; in-depth are appended."""
        if depth > self.config.max_rebuttal_depth:
            return RebuttalResult(refused=True, refuse_reason="rebuttal_depth_exceeded")
        if record.timing is None:
            return RebuttalResult(refused=True, refuse_reason="no_run_record")
        side = record.assignments.get(participant_id, PROPOSITION)
        speaker = speakers.get(participant_id)
        if speaker is None:
            return RebuttalResult(refused=True, refuse_reason="unknown_participant")
        conclusion, text = speaker.conclude(record.motion, side)
        turn = Turn(
            participant_id=participant_id,
            side=side,
            kind="rebuttal",
            depth=int(depth),
            text=text,
            conclusion=conclusion,
            elapsed_ms=int(getattr(speaker, "elapsed_ms", 0)),
        )
        turn = self.loop.execute(turn, self.config.turn_budget_ms)
        if turn.timed_out:
            record.timing.overruns.append(f"{participant_id}:rebuttal:d{depth}")
        record.turns.append(turn)
        return RebuttalResult(refused=False, turn=turn)


def _conclusions_under(
    motion: Motion,
    speakers: dict[str, Any],
    assignments: dict[str, str],
    config: DebateConfig,
) -> dict[str, str]:
    record = OxfordProtocol(config).run(motion, speakers, assignments)
    return record.conclusions()


def _swap_sides(assignments: dict[str, str]) -> dict[str, str]:
    return {
        pid: (OPPOSITION if side == PROPOSITION else PROPOSITION)
        for pid, side in assignments.items()
    }


def _flip_rate(base: dict[str, str], after: dict[str, str]) -> tuple[float, int]:
    if not base:
        return 0.0, 0
    flips = sum(1 for pid, c in base.items() if after.get(pid) != c)
    return flips / len(base), flips


def side_swap_experiment(
    motion: Motion,
    speakers: dict[str, Any],
    assignments: dict[str, str],
    config: DebateConfig,
) -> dict[str, Any]:
    """Run the same motion with every side swapped; publish the conclusion flip rate."""
    base = _conclusions_under(motion, speakers, assignments, config)
    swapped = _swap_sides(assignments)
    after = _conclusions_under(motion, speakers, swapped, config)
    rate, flips = _flip_rate(base, after)
    return {
        "experiment": "side-swap",
        "motion_id": motion.motion_id,
        "evidence_decisive": bool(motion.decisive),
        "n_speakers": len(base),
        "flips": flips,
        "flip_rate": rate,
        "swap_map": swapped,
    }


def evidence_swap_experiment(
    motion: Motion,
    speakers: dict[str, Any],
    assignments: dict[str, str],
    config: DebateConfig,
) -> dict[str, Any]:
    """Reverse the evidence polarity, keep sides; publish the conclusion flip rate."""
    base = _conclusions_under(motion, speakers, assignments, config)
    after = _conclusions_under(motion.swap_evidence(), speakers, assignments, config)
    rate, flips = _flip_rate(base, after)
    return {
        "experiment": "evidence-swap",
        "motion_id": motion.motion_id,
        "evidence_decisive": bool(motion.decisive),
        "n_speakers": len(base),
        "flips": flips,
        "flip_rate": rate,
    }


def compare_side_vs_evidence(
    motion: Motion,
    speakers: dict[str, Any],
    assignments: dict[str, str],
    config: DebateConfig,
) -> dict[str, Any]:
    """The unit's falsifiable question, measured: side effect minus evidence effect."""
    side = side_swap_experiment(motion, speakers, assignments, config)
    ev = evidence_swap_experiment(motion, speakers, assignments, config)
    delta = float(side["flip_rate"]) - float(ev["flip_rate"])
    exceeds = delta > 0
    return {
        "experiment": "side-vs-evidence",
        "motion_id": motion.motion_id,
        "evidence_decisive": bool(motion.decisive),
        "side_assignment_flip_rate": float(side["flip_rate"]),
        "evidence_flip_rate": float(ev["flip_rate"]),
        "side_minus_evidence": delta,
        "side_exceeds_evidence": exceeds,
        "interpretation": (
            "side assignment changes conclusions more than evidence"
            if exceeds
            else "evidence changes conclusions as much as or more than side assignment"
        ),
    }


__all__ = [
    "DebateConfig",
    "DebateRecord",
    "EvidenceBoundSpeaker",
    "HIGH_FLIP_FLOOR",
    "LOW_FLIP_CEILING",
    "LocalTurnLoop",
    "Motion",
    "OPPOSITION",
    "OxfordProtocol",
    "PROPOSITION",
    "RebuttalResult",
    "SideBoundSpeaker",
    "TimingAudit",
    "Turn",
    "balanced_taste_motion",
    "compare_side_vs_evidence",
    "decisive_arithmetic_motion",
    "evidence_swap_experiment",
    "side_swap_experiment",
]
