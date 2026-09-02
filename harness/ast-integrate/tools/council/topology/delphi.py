"""Delphi topology: anonymous rounds, evidence-gated revision, herding control.

Classical Delphi feeds each panelist the panel's round-1 distribution and asks
for a revised estimate. Its known failure is herding: a majority-wrong cluster
pulls everyone toward the round-1 median, dispersion collapses, and the shrink
is then sold as "convergence" although the median never moved toward truth.

This module keeps the anonymous feedback (an identity-free distributional
summary) but gates revision on private evidence: a panelist whose evidence is
at or above :data:`EVIDENCE_GATE` holds their estimate, and only weak-evidence
panelists adopt the feedback median. The *holdout median* (over high-evidence
panelists) is the panel's answer; the classical full-panel median is still
reported so the two can be compared against ground truth on known-answer
questions. Dispersion is reported, never used as the success criterion.

Two experiments are the unit's falsifiable contract: ten known-answer
questions where the round-1 median is majority-wrong, and a planted-wrong
median negative control with an ungated ablation that must follow the plant.
A leak scanner proves the feedback carries no panelist identities and fires
on an injected one.
"""

from __future__ import annotations

import random
import statistics
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

SCHEMA = "council.topology.delphi.v1"
EVIDENCE_GATE = 0.6
DISTINGUISHABLE_FRACTION = 0.5  # |r1 median - truth| must exceed this many scales
ANCHOR_TOLERANCE_FRACTION = 0.25  # r2 median within this many scales of the anchor
IDENTITY_KEYS = frozenset(
    {"panelist_id", "panelist", "author", "author_id", "seat", "seat_id"}
)
PLANT_OFFSET_SCALES = 8.0


class DelphiError(ValueError):
    """Panel or round contract violation."""


@dataclass(frozen=True)
class Question:
    question_id: str
    text: str
    truth: float
    scale: float
    unit: str = ""


@dataclass(frozen=True)
class Panelist:
    panelist_id: str
    evidence: float  # 0..1 strength of private evidence
    private_estimate: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.evidence <= 1.0:
            raise DelphiError(
                f"{self.panelist_id}: evidence {self.evidence} outside [0, 1]"
            )

    @property
    def high_evidence(self) -> bool:
        return self.evidence >= EVIDENCE_GATE


@dataclass(frozen=True)
class Estimate:
    panelist_id: str
    round: int
    value: float
    evidence: float
    rationale: str


@dataclass(frozen=True)
class Turn:
    turn_id: str
    round: int
    panelist_id: str
    value: float


@dataclass(frozen=True)
class Feedback:
    """Anonymised distributional summary fed back between rounds."""

    round: int
    n: int
    median: float
    q1: float
    q3: float
    iqr: float
    minimum: float
    maximum: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "round": self.round,
            "n": self.n,
            "median": self.median,
            "q1": self.q1,
            "q3": self.q3,
            "iqr": self.iqr,
            "min": self.minimum,
            "max": self.maximum,
        }


@dataclass
class DelphiResult:
    question: Question
    panel: tuple[Panelist, ...]
    gated: bool
    round1: list[Estimate]
    feedback: Feedback
    anchor: float
    round2: list[Estimate]
    turns: list[Turn] = field(default_factory=list)

    @property
    def r1_values(self) -> list[float]:
        return [e.value for e in self.round1]

    @property
    def r2_values(self) -> list[float]:
        return [e.value for e in self.round2]

    @property
    def holdout_values(self) -> list[float]:
        high = {p.panelist_id for p in self.panel if p.high_evidence}
        return [e.value for e in self.round2 if e.panelist_id in high]

    @property
    def turns_match_estimates(self) -> bool:
        return len(self.turns) == len(self.round1) + len(self.round2)


def _quartiles(values: Sequence[float]) -> tuple[float, float]:
    ordered = sorted(values)
    if len(ordered) < 2:
        v = ordered[0] if ordered else 0.0
        return v, v
    q = statistics.quantiles(ordered, n=4, method="inclusive")
    return q[0], q[2]


def summarize(values: Sequence[float], *, round_no: int) -> Feedback:
    if not values:
        raise DelphiError("cannot summarise an empty round")
    q1, q3 = _quartiles(values)
    return Feedback(
        round=round_no,
        n=len(values),
        median=statistics.median(values),
        q1=q1,
        q3=q3,
        iqr=q3 - q1,
        minimum=min(values),
        maximum=max(values),
    )


def revise(panelist: Panelist, anchor: float, *, gated: bool) -> float:
    """Round-2 rule. Gated: high-evidence panelists hold, weak-evidence
    panelists adopt the anchor. Ungated (classical ablation): everyone adopts."""
    if gated and panelist.high_evidence:
        return panelist.private_estimate
    return anchor


def run_delphi(
    question: Question,
    panel: Sequence[Panelist],
    *,
    gated: bool = True,
    feedback_override: float | None = None,
) -> DelphiResult:
    """Two Delphi rounds. ``feedback_override`` replaces the median shown to
    the panel (used to plant a wrong median); the honest summary is otherwise
    what the panel sees."""
    if len(panel) < 3:
        raise DelphiError("a Delphi panel needs at least three panelists")
    ids = [p.panelist_id for p in panel]
    if len(set(ids)) != len(ids):
        raise DelphiError(f"duplicate panelist ids {ids}")
    turns: list[Turn] = []

    def record(round_no: int, pid: str, value: float) -> None:
        turns.append(
            Turn(
                turn_id=f"t-{len(turns) + 1}",
                round=round_no,
                panelist_id=pid,
                value=value,
            )
        )

    round1 = []
    for p in panel:
        round1.append(
            Estimate(
                p.panelist_id, 1, p.private_estimate, p.evidence, "private estimate"
            )
        )
        record(1, p.panelist_id, p.private_estimate)
    feedback = summarize([e.value for e in round1], round_no=1)
    anchor = feedback.median if feedback_override is None else float(feedback_override)

    round2 = []
    for p in panel:
        value = revise(p, anchor, gated=gated)
        why = (
            "held private estimate (evidence at/above gate)"
            if gated and p.high_evidence
            else "adopted feedback median"
        )
        round2.append(Estimate(p.panelist_id, 2, value, p.evidence, why))
        record(2, p.panelist_id, value)
    return DelphiResult(
        question=question,
        panel=tuple(panel),
        gated=gated,
        round1=round1,
        feedback=feedback,
        anchor=anchor,
        round2=round2,
        turns=turns,
    )


def feedback_payload(feedback: Feedback, anchor: float) -> dict[str, Any]:
    """Exactly what panelists receive between rounds."""
    payload = feedback.as_dict()
    payload["median"] = anchor
    return payload


def scan_feedback_for_identities(
    payload: Any, panelist_ids: Iterable[str]
) -> list[str]:
    """Return every identity leak in a feedback payload: an identity-shaped
    key, or a string that contains a panelist id."""
    ids = [str(i) for i in panelist_ids]
    hits: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, Mapping):
            for k, v in node.items():
                if str(k) in IDENTITY_KEYS:
                    hits.append(f"key:{k}")
                walk(v)
        elif isinstance(node, (list, tuple)):
            for v in node:
                walk(v)
        elif isinstance(node, str):
            hits.extend(pid for pid in ids if pid and pid in node)

    walk(payload)
    return hits


def anchoring_sacrifices(result: DelphiResult) -> int:
    """High-evidence panelists who moved toward the anchor and away from truth."""
    truth = result.question.truth
    high = {p.panelist_id for p in result.panel if p.high_evidence}
    r1 = {e.panelist_id: e.value for e in result.round1}
    count = 0
    for e in result.round2:
        if e.panelist_id not in high:
            continue
        before, after = r1[e.panelist_id], e.value
        toward_anchor = abs(after - result.anchor) < abs(before - result.anchor)
        away_from_truth = abs(after - truth) > abs(before - truth)
        if toward_anchor and away_from_truth:
            count += 1
    return count


def anchoring_detected(result: DelphiResult) -> bool:
    """Did the panel jump to an anchor its own round-1 distribution did not
    support? True when the round-2 median lands within tolerance of the anchor
    while the anchor lay outside the round-1 interquartile range."""
    fb = result.feedback
    tol = ANCHOR_TOLERANCE_FRACTION * result.question.scale
    anchor_outside_r1 = not (fb.q1 - tol <= result.anchor <= fb.q3 + tol)
    r2_median = statistics.median(result.r2_values)
    return anchor_outside_r1 and abs(r2_median - result.anchor) <= tol


def anchoring_finding(result: DelphiResult) -> dict[str, Any] | None:
    if not anchoring_detected(result):
        return None
    return {
        "kind": "ANCHORING",
        "question_id": result.question.question_id,
        "anchor": result.anchor,
        "r1_median": result.feedback.median,
        "r1_iqr": [result.feedback.q1, result.feedback.q3],
        "r2_median": statistics.median(result.r2_values),
        "gated": result.gated,
        "message": "panel followed a feedback anchor its own round-1 distribution did not support",
    }


# --------------------------------------------------------------------------
# Known-answer material
# --------------------------------------------------------------------------

KNOWN_QUESTIONS: tuple[Question, ...] = (
    Question("q01", "Speed of light in vacuum", 299792.458, 5000.0, "km/s"),
    Question("q02", "Boiling point of water at 1 atm", 373.15, 10.0, "K"),
    Question("q03", "Mean radius of Earth", 6371.0, 400.0, "km"),
    Question("q04", "Mean Earth-Moon distance", 384400.0, 20000.0, "km"),
    Question("q05", "Height of Everest above sea level", 8849.0, 300.0, "m"),
    Question("q06", "Normal human body temperature", 37.0, 1.0, "C"),
    Question("q07", "Length of a Julian year", 365.25, 5.0, "days"),
    Question("q08", "Bones in an adult human skeleton", 206.0, 10.0, "count"),
    Question("q09", "Density of liquid water at 4 C", 1000.0, 30.0, "kg/m3"),
    Question("q10", "Speed of sound in air at 20 C", 343.0, 20.0, "m/s"),
)


def majority_wrong_panel(
    question: Question,
    rng: random.Random,
    *,
    n_high: int = 3,
    n_low: int = 6,
) -> tuple[Panelist, ...]:
    """A panel whose weak-evidence majority clusters several scales away from
    truth while a high-evidence minority sits near it."""
    bias = rng.choice((-1.0, 1.0)) * rng.uniform(5.0, 9.0) * question.scale
    panel: list[Panelist] = []
    for i in range(n_high):
        est = question.truth + rng.gauss(0.0, 0.02) * question.scale
        panel.append(
            Panelist(f"{question.question_id}-hi-{i}", rng.uniform(0.75, 0.95), est)
        )
    for i in range(n_low):
        est = question.truth + bias + rng.gauss(0.0, 0.3) * question.scale
        panel.append(
            Panelist(f"{question.question_id}-lo-{i}", rng.uniform(0.1, 0.4), est)
        )
    return tuple(panel)


def calibrated_panel(
    question: Question, rng: random.Random, *, n: int = 9
) -> tuple[Panelist, ...]:
    """Nine well-evidenced panelists scattered tightly around truth."""
    return tuple(
        Panelist(
            f"cal-{question.question_id}-{i}",
            rng.uniform(0.7, 0.95),
            question.truth + rng.gauss(0.0, 0.05) * question.scale,
        )
        for i in range(n)
    )


def evaluate_known_answer(result: DelphiResult) -> dict[str, Any]:
    q = result.question
    r1 = summarize(result.r1_values, round_no=1)
    r2 = summarize(result.r2_values, round_no=2)
    holdout = result.holdout_values
    holdout_median = statistics.median(holdout) if holdout else float("nan")
    err_r1 = abs(r1.median - q.truth)
    err_r2 = abs(r2.median - q.truth)
    err_hold = abs(holdout_median - q.truth) if holdout else float("inf")
    distinguishable = err_r1 > DISTINGUISHABLE_FRACTION * q.scale
    return {
        "question_id": q.question_id,
        "truth": q.truth,
        "scale": q.scale,
        "r1_median": r1.median,
        "r2_median": r2.median,
        "holdout_median": holdout_median,
        "abs_err_r1_median": err_r1,
        "abs_err_r2_median": err_r2,
        "abs_err_holdout_median": err_hold,
        "r1_iqr": r1.iqr,
        "r2_iqr": r2.iqr,
        "n_holdouts": len(holdout),
        "distinguishable_median_vs_truth": distinguishable,
        "holdout_closer_to_truth_than_classical": err_hold < err_r2,
        "herding_dispersion_fell_accuracy_did_not": r2.iqr < r1.iqr
        and err_r2 >= err_r1 - 1e-9,
        "high_evidence_anchoring_sacrifices": anchoring_sacrifices(result),
        "turns_match_estimates": result.turns_match_estimates,
    }


KNOWN_ANSWER_PASS_RULE = (
    "10 known-answer questions; round-1 median distinguishable from truth on >=8; "
    "evidence-gated holdout median closer to truth than classical round-2 median on every "
    "distinguishable question; zero high-evidence panelists who moved toward the round-1 "
    "median at the expense of truth. Dispersion is reported but a dispersion-only "
    "'convergence' claim is the herding overclaim this unit forbids. Turn log count equals "
    "estimates."
)


def experiment_known_answers(seed: int = 286) -> dict[str, Any]:
    rng = random.Random(seed)
    rows = []
    for q in KNOWN_QUESTIONS:
        panel = majority_wrong_panel(q, rng)
        rows.append(evaluate_known_answer(run_delphi(q, panel, gated=True)))
    distinguishable = [r for r in rows if r["distinguishable_median_vs_truth"]]
    holdout_wins = sum(
        1 for r in distinguishable if r["holdout_closer_to_truth_than_classical"]
    )
    sacrifices = sum(r["high_evidence_anchoring_sacrifices"] for r in rows)
    herding = sum(1 for r in rows if r["herding_dispersion_fell_accuracy_did_not"])
    turns_ok = all(r["turns_match_estimates"] for r in rows)
    passed = (
        len(rows) == 10
        and len(distinguishable) >= 8
        and holdout_wins == len(distinguishable)
        and sacrifices == 0
        and turns_ok
    )
    return {
        "schema": SCHEMA,
        "experiment": "known-answer-convergence",
        "seed": seed,
        "n_questions": len(rows),
        "n_distinguishable": len(distinguishable),
        "holdout_closer_than_classical_on_distinguishable": holdout_wins,
        "high_evidence_anchoring_sacrifices": sacrifices,
        "herding_flags": herding,
        "turns_match_estimates": turns_ok,
        "mean_abs_err_r1_median": statistics.fmean(
            r["abs_err_r1_median"] for r in rows
        ),
        "mean_abs_err_r2_median": statistics.fmean(
            r["abs_err_r2_median"] for r in rows
        ),
        "mean_abs_err_holdout": statistics.fmean(
            r["abs_err_holdout_median"] for r in rows
        ),
        "passed": passed,
        "pass_rule": KNOWN_ANSWER_PASS_RULE,
        "rows": rows,
    }


PLANTED_PASS_RULE = (
    "Planted median = truth + 8*scale on a calibrated panel. Gated panel must not follow the "
    "plant (no ANCHORING finding); the ungated ablation must follow it (both-states); honest "
    "feedback must not flag anchoring; the feedback payload carries no panelist identity and "
    "the leak scanner fires on an injected panelist_id. Turn log count equals estimates."
)


def experiment_planted_median(
    seed: int = 286, question_id: str = "q03"
) -> dict[str, Any]:
    q = next((x for x in KNOWN_QUESTIONS if x.question_id == question_id), None)
    if q is None:
        raise DelphiError(f"unknown question {question_id}")
    rng = random.Random(seed)
    panel = calibrated_panel(q, rng)
    plant = q.truth + PLANT_OFFSET_SCALES * q.scale

    gated = run_delphi(q, panel, gated=True, feedback_override=plant)
    ungated = run_delphi(q, panel, gated=False, feedback_override=plant)
    honest = run_delphi(q, panel, gated=True)

    ids = [p.panelist_id for p in panel]
    clean_payload = feedback_payload(gated.feedback, gated.anchor)
    clean_hits = scan_feedback_for_identities(clean_payload, ids)
    injected_payload = dict(clean_payload)
    injected_payload["panelist_id"] = ids[0]
    injected_hits = scan_feedback_for_identities(injected_payload, ids)

    def mean_abs(values: Sequence[float], target: float) -> float:
        return statistics.fmean(abs(v - target) for v in values)

    finding = anchoring_finding(gated)
    gated_detected = anchoring_detected(gated)
    ungated_detected = anchoring_detected(ungated)
    honest_detected = anchoring_detected(honest)
    passed = (
        not gated_detected
        and finding is None
        and ungated_detected
        and not honest_detected
        and bool(injected_hits)
        and not clean_hits
        and gated.turns_match_estimates
    )
    return {
        "schema": SCHEMA,
        "experiment": "planted-wrong-median",
        "seed": seed,
        "question_id": q.question_id,
        "truth": q.truth,
        "scale": q.scale,
        "planted_median": plant,
        "gated_anchoring_detected": gated_detected,
        "ungated_ablation_anchoring_detected": ungated_detected,
        "honest_feedback_anchoring_detected": honest_detected,
        "gated_mean_abs_to_truth_r2": mean_abs(gated.r2_values, q.truth),
        "gated_mean_abs_to_plant_r2": mean_abs(gated.r2_values, plant),
        "ungated_mean_abs_to_truth_r2": mean_abs(ungated.r2_values, q.truth),
        "ungated_mean_abs_to_plant_r2": mean_abs(ungated.r2_values, plant),
        "gated_r2_median": statistics.median(gated.r2_values),
        "ungated_r2_median": statistics.median(ungated.r2_values),
        "leak_scanner_fired_on_injected_id": bool(injected_hits),
        "leak_scanner_silent_on_clean_feedback": not clean_hits,
        "leak_hits_injected": injected_hits,
        "anchoring_finding": finding,
        "turns_match_gated": gated.turns_match_estimates,
        "passed": passed,
        "pass_rule": PLANTED_PASS_RULE,
    }


__all__ = [
    "ANCHOR_TOLERANCE_FRACTION",
    "DISTINGUISHABLE_FRACTION",
    "EVIDENCE_GATE",
    "IDENTITY_KEYS",
    "KNOWN_QUESTIONS",
    "PLANT_OFFSET_SCALES",
    "SCHEMA",
    "DelphiError",
    "DelphiResult",
    "Estimate",
    "Feedback",
    "Panelist",
    "Question",
    "Turn",
    "anchoring_detected",
    "anchoring_finding",
    "anchoring_sacrifices",
    "calibrated_panel",
    "evaluate_known_answer",
    "experiment_known_answers",
    "experiment_planted_median",
    "feedback_payload",
    "majority_wrong_panel",
    "revise",
    "run_delphi",
    "scan_feedback_for_identities",
    "summarize",
]
