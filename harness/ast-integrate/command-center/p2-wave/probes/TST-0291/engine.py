"""Delphi topology runtime for TST-0291.

Premise under test: iterated anonymous feedback is not a convergence claim
until BOTH round-over-round dispersion AND accuracy against ground truth are
measured. Falling IQR with flat or worsening MAE is herding. The runtime
refuses a confident consensus on a herding trajectory.

tools/council/simulate.py (TST-0257) and tools/council/topology/delphi.py
(IMP-0286) are catalog inputs and are not on this worktree. This module is
the contracted SUT for the calibration probe.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping

HERE = Path(__file__).resolve().parent
QUESTIONS_PATH = HERE / "questions.json"

FeedbackMode = Literal["anonymous", "attributed"]
KIND_CONVERGENCE = "CONVERGENCE"
KIND_HERDING = "HERDING"
KIND_NO_TIGHTENING = "NO_TIGHTENING"
KIND_INCONCLUSIVE = "INCONCLUSIVE"

N_ROUNDS = 6
N_SEATS = 7
ANON_LISTEN = 0.55
ATTR_PRIVATE = 0.10
ATTR_MEDIAN = 0.15
ATTR_LEADER = 0.75
IMPROVE_RATIO = 0.92
WORSEN_RATIO = 1.08
TIGHTEN_RATIO = 0.92

# Relative private-signal offsets for the six (or seven) updating seats.
HONEST_OFFSETS = (-0.22, -0.14, -0.07, 0.03, 0.11, 0.18, 0.26)
HONEST_CONFIDENCE = (0.42, 0.38, 0.47, 0.40, 0.44, 0.36, 0.41)
PLANT_RELATIVE = 2.6
PLANT_CONFIDENCE = 0.99
PLANT_SEAT = "seat-plant"


@dataclass(frozen=True)
class Question:
    id: str
    prompt: str
    truth: float
    unit: str


@dataclass
class Seat:
    seat_id: str
    private: float
    confidence: float
    stubborn: bool
    estimate: float


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def sha256_obj(obj: Any) -> str:
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()


def load_questions(path: Path | None = None) -> list[Question]:
    raw = json.loads((path or QUESTIONS_PATH).read_text(encoding="utf-8"))
    out: list[Question] = []
    for row in raw.get("questions") or []:
        out.append(
            Question(
                id=str(row["id"]),
                prompt=str(row["prompt"]),
                truth=float(row["truth"]),
                unit=str(row.get("unit") or ""),
            )
        )
    if len(out) < 8:
        raise ValueError("scored set must contain at least 8 items")
    return out


def scale_of(truth: float) -> float:
    return max(abs(float(truth)), 1.0)


def percentile(xs: list[float], p: float) -> float:
    ys = sorted(float(x) for x in xs)
    if not ys:
        raise ValueError("percentile of empty sample")
    if len(ys) == 1:
        return ys[0]
    k = (len(ys) - 1) * p
    lo = int(math.floor(k))
    hi = int(math.ceil(k))
    if lo == hi:
        return ys[lo]
    w = k - lo
    return ys[lo] * (1.0 - w) + ys[hi] * w


def iqr(xs: list[float]) -> float:
    return percentile(xs, 0.75) - percentile(xs, 0.25)


def median(xs: list[float]) -> float:
    ys = sorted(float(x) for x in xs)
    n = len(ys)
    if n == 0:
        raise ValueError("median of empty sample")
    mid = n // 2
    if n % 2:
        return ys[mid]
    return 0.5 * (ys[mid - 1] + ys[mid])


def mean(xs: Iterable[float]) -> float:
    vals = [float(x) for x in xs]
    if not vals:
        raise ValueError("mean of empty sample")
    return sum(vals) / len(vals)


def pstdev(xs: list[float]) -> float:
    vals = [float(x) for x in xs]
    if len(vals) < 2:
        return 0.0
    m = mean(vals)
    return math.sqrt(sum((x - m) ** 2 for x in vals) / len(vals))


def mae(xs: list[float], truth: float) -> float:
    return mean(abs(x - truth) for x in xs)


def group_abs_error(xs: list[float], truth: float) -> float:
    return abs(median(xs) - truth)


def make_seats(question: Question, *, planted: bool) -> list[Seat]:
    scale = scale_of(question.truth)
    seats: list[Seat] = []
    honest_n = N_SEATS - 1 if planted else N_SEATS
    for i in range(honest_n):
        private = question.truth + HONEST_OFFSETS[i] * scale
        seats.append(
            Seat(
                seat_id=f"seat-{i:02d}",
                private=private,
                confidence=HONEST_CONFIDENCE[i],
                stubborn=False,
                estimate=private,
            )
        )
    if planted:
        private = question.truth + PLANT_RELATIVE * scale
        seats.append(
            Seat(
                seat_id=PLANT_SEAT,
                private=private,
                confidence=PLANT_CONFIDENCE,
                stubborn=True,
                estimate=private,
            )
        )
    return seats


def _feedback_payload(seats: list[Seat], mode: FeedbackMode) -> dict[str, Any]:
    estimates = [s.estimate for s in seats]
    payload: dict[str, Any] = {
        "mode": mode,
        "n": len(seats),
        "median": median(estimates),
        "iqr": iqr(estimates),
        "mean": mean(estimates),
    }
    if mode == "attributed":
        payload["attributed_estimates"] = [
            {
                "seat_id": s.seat_id,
                "estimate": s.estimate,
                "confidence": s.confidence,
            }
            for s in seats
        ]
        leader = max(seats, key=lambda s: (s.confidence, s.seat_id))
        payload["leader_seat_id"] = leader.seat_id
        payload["leader_estimate"] = leader.estimate
        payload["leader_confidence"] = leader.confidence
    else:
        payload["attributed_estimates"] = None
        payload["leader_seat_id"] = None
        payload["leader_estimate"] = None
        payload["leader_confidence"] = None
    return payload


def _revise(seat: Seat, fb: Mapping[str, Any], mode: FeedbackMode) -> float:
    if seat.stubborn:
        return seat.estimate
    med = float(fb["median"])
    if mode == "anonymous":
        # Evidence-retaining Delphi: private signal mixed with anonymous median.
        return (1.0 - ANON_LISTEN) * seat.private + ANON_LISTEN * med
    leader = float(fb["leader_estimate"])
    # Attribution lets the named high-confidence seat dominate revision.
    return ATTR_PRIVATE * seat.private + ATTR_MEDIAN * med + ATTR_LEADER * leader


def round_metrics(seats: list[Seat], truth: float, round_idx: int) -> dict[str, Any]:
    estimates = [s.estimate for s in seats]
    return {
        "round": round_idx,
        "n": len(estimates),
        "estimates": [
            {
                "seat_id": s.seat_id,
                "estimate": s.estimate,
                "confidence": s.confidence,
                "stubborn": s.stubborn,
            }
            for s in seats
        ],
        "median": median(estimates),
        "mean": mean(estimates),
        "stdev": pstdev(estimates),
        "iqr": iqr(estimates),
        "individual_mae": mae(estimates, truth),
        "group_abs_error": group_abs_error(estimates, truth),
        "truth": truth,
    }


def classify_trajectory(rounds: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Classify from first/last round raw numbers.

    CONVERGENCE requires falling dispersion AND improving individual MAE,
    with group (median) error not worsening. Dispersion-alone is herding
    or inconclusive, never a confident consensus.
    """
    if len(rounds) < 2:
        raise ValueError("need at least two rounds")
    first, last = rounds[0], rounds[-1]
    iqr0, iqr1 = float(first["iqr"]), float(last["iqr"])
    mae0, mae1 = float(first["individual_mae"]), float(last["individual_mae"])
    g0, g1 = float(first["group_abs_error"]), float(last["group_abs_error"])
    dispersion_fell = iqr1 < iqr0 * TIGHTEN_RATIO
    mae_improved = mae1 < mae0 * IMPROVE_RATIO
    mae_worsened = mae1 > mae0 * WORSEN_RATIO
    group_worsened = g1 > g0 * WORSEN_RATIO
    if not dispersion_fell:
        kind = KIND_NO_TIGHTENING
        allow = False
        reason = "dispersion_did_not_fall"
    elif mae_improved and not group_worsened:
        kind = KIND_CONVERGENCE
        allow = True
        reason = "dispersion_fell_and_accuracy_improved"
    elif mae_worsened or group_worsened:
        kind = KIND_HERDING
        allow = False
        reason = "dispersion_fell_with_worsening_accuracy"
    else:
        kind = KIND_HERDING
        allow = False
        reason = "dispersion_fell_with_flat_accuracy"
    return {
        "kind": kind,
        "allow_confident_consensus": allow,
        "reason": reason,
        "dispersion_fell": dispersion_fell,
        "mae_improved": mae_improved,
        "mae_worsened": mae_worsened,
        "group_worsened": group_worsened,
        "iqr_first": iqr0,
        "iqr_last": iqr1,
        "mae_first": mae0,
        "mae_last": mae1,
        "group_abs_error_first": g0,
        "group_abs_error_last": g1,
        "iqr_ratio": (iqr1 / iqr0) if iqr0 else None,
        "mae_ratio": (mae1 / mae0) if mae0 else None,
        "group_error_ratio": (g1 / g0) if g0 else None,
    }


def naive_dispersion_only_claim(rounds: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Overclaim this unit exists to forbid: IQR fell, therefore convergence."""
    first, last = rounds[0], rounds[-1]
    iqr0, iqr1 = float(first["iqr"]), float(last["iqr"])
    fell = iqr1 < iqr0 * TIGHTEN_RATIO
    return {
        "kind": KIND_CONVERGENCE if fell else KIND_NO_TIGHTENING,
        "allow_confident_consensus": bool(fell),
        "reason": "dispersion_fell" if fell else "dispersion_did_not_fall",
        "overclaim": True,
    }


def maybe_report_consensus(classification: Mapping[str, Any]) -> dict[str, Any]:
    allow = bool(classification.get("allow_confident_consensus"))
    kind = str(classification.get("kind") or "")
    if allow and kind == KIND_CONVERGENCE:
        return {
            "confident_consensus": True,
            "withheld": False,
            "withheld_reason": None,
            "classification": kind,
        }
    withheld_reason = "herding" if kind == KIND_HERDING else str(
        classification.get("reason") or kind or "not_convergence"
    )
    return {
        "confident_consensus": False,
        "withheld": True,
        "withheld_reason": withheld_reason,
        "classification": kind,
    }


def run_question(
    question: Question,
    *,
    planted: bool,
    mode: FeedbackMode,
    n_rounds: int = N_ROUNDS,
) -> dict[str, Any]:
    seats = make_seats(question, planted=planted)
    rounds: list[dict[str, Any]] = []
    feedback_log: list[dict[str, Any]] = []
    for r in range(n_rounds):
        metrics = round_metrics(seats, question.truth, r)
        rounds.append(metrics)
        fb = _feedback_payload(seats, mode)
        feedback_log.append(fb)
        if r == n_rounds - 1:
            break
        for seat in seats:
            seat.estimate = _revise(seat, fb, mode)
    classification = classify_trajectory(rounds)
    naive = naive_dispersion_only_claim(rounds)
    consensus = maybe_report_consensus(classification)
    return {
        "question_id": question.id,
        "prompt": question.prompt,
        "truth": question.truth,
        "unit": question.unit,
        "planted": planted,
        "mode": mode,
        "n_rounds": n_rounds,
        "rounds": rounds,
        "feedback": feedback_log,
        "classification": classification,
        "naive_dispersion_only": naive,
        "consensus": consensus,
        "overclaim_disagreement": naive["kind"] != classification["kind"]
        or naive["allow_confident_consensus"] != classification["allow_confident_consensus"],
    }


def run_panel(
    questions: list[Question] | None = None,
    *,
    planted: bool,
    mode: FeedbackMode,
    n_rounds: int = N_ROUNDS,
) -> dict[str, Any]:
    qs = questions if questions is not None else load_questions()
    per = [run_question(q, planted=planted, mode=mode, n_rounds=n_rounds) for q in qs]
    kinds = [p["classification"]["kind"] for p in per]
    counts = {
        KIND_CONVERGENCE: kinds.count(KIND_CONVERGENCE),
        KIND_HERDING: kinds.count(KIND_HERDING),
        KIND_NO_TIGHTENING: kinds.count(KIND_NO_TIGHTENING),
        KIND_INCONCLUSIVE: kinds.count(KIND_INCONCLUSIVE),
    }
    # Panel-level per-round means of the raw metrics (unweighted across items).
    per_round: list[dict[str, Any]] = []
    for r in range(n_rounds):
        iqr_r = [p["rounds"][r]["iqr"] for p in per]
        mae_r = [p["rounds"][r]["individual_mae"] for p in per]
        g_r = [p["rounds"][r]["group_abs_error"] for p in per]
        rel_iqr = [
            p["rounds"][r]["iqr"] / scale_of(p["truth"]) for p in per
        ]
        rel_mae = [
            p["rounds"][r]["individual_mae"] / scale_of(p["truth"]) for p in per
        ]
        per_round.append(
            {
                "round": r,
                "mean_iqr": mean(iqr_r),
                "mean_individual_mae": mean(mae_r),
                "mean_group_abs_error": mean(g_r),
                "mean_relative_iqr": mean(rel_iqr),
                "mean_relative_mae": mean(rel_mae),
            }
        )
    consensus_allowed = [
        p["consensus"]["confident_consensus"] for p in per
    ]
    herding_any = counts[KIND_HERDING] > 0
    # A panel reports confident consensus only if EVERY item is CONVERGENCE.
    panel_allow = counts[KIND_CONVERGENCE] == len(per) and not herding_any
    transcript = {
        "planted": planted,
        "mode": mode,
        "n_questions": len(per),
        "n_rounds": n_rounds,
        "kind_counts": counts,
        "per_question": per,
        "per_round_means": per_round,
        "panel_classification": {
            "kind": KIND_CONVERGENCE
            if panel_allow
            else (KIND_HERDING if herding_any else KIND_NO_TIGHTENING),
            "allow_confident_consensus": panel_allow,
            "herding_items": counts[KIND_HERDING],
            "convergence_items": counts[KIND_CONVERGENCE],
            "confident_consensus_count": sum(1 for x in consensus_allowed if x),
        },
    }
    transcript["transcript_sha256"] = sha256_obj(
        {
            "planted": planted,
            "mode": mode,
            "per_question_estimates": [
                [row["estimates"] for row in p["rounds"]] for p in per
            ],
        }
    )
    return transcript


def anonymity_contrast(
    questions: list[Question] | None = None,
    *,
    planted: bool = True,
    n_rounds: int = N_ROUNDS,
) -> dict[str, Any]:
    qs = questions if questions is not None else load_questions()
    anon = run_panel(qs, planted=planted, mode="anonymous", n_rounds=n_rounds)
    attr = run_panel(qs, planted=planted, mode="attributed", n_rounds=n_rounds)
    last_a = anon["per_round_means"][-1]
    last_t = attr["per_round_means"][-1]
    first_a = anon["per_round_means"][0]
    first_t = attr["per_round_means"][0]
    return {
        "planted": planted,
        "anonymous": {
            "kind_counts": anon["kind_counts"],
            "panel": anon["panel_classification"],
            "per_round_means": anon["per_round_means"],
            "transcript_sha256": anon["transcript_sha256"],
        },
        "attributed": {
            "kind_counts": attr["kind_counts"],
            "panel": attr["panel_classification"],
            "per_round_means": attr["per_round_means"],
            "transcript_sha256": attr["transcript_sha256"],
        },
        "delta": {
            "final_mean_relative_mae_attributed_minus_anonymous": last_t["mean_relative_mae"]
            - last_a["mean_relative_mae"],
            "final_mean_group_abs_error_attributed_minus_anonymous": last_t[
                "mean_group_abs_error"
            ]
            - last_a["mean_group_abs_error"],
            "anonymous_herding_items": anon["kind_counts"][KIND_HERDING],
            "attributed_herding_items": attr["kind_counts"][KIND_HERDING],
            "anonymous_allow_consensus": anon["panel_classification"][
                "allow_confident_consensus"
            ],
            "attributed_allow_consensus": attr["panel_classification"][
                "allow_confident_consensus"
            ],
            "first_round_relative_mae_equal": abs(
                first_a["mean_relative_mae"] - first_t["mean_relative_mae"]
            )
            < 1e-12,
        },
        "_anonymous_full": anon,
        "_attributed_full": attr,
    }


def seats_as_dicts(seats: list[Seat]) -> list[dict[str, Any]]:
    return [asdict(s) for s in seats]


def production_simulate_present(repo: Path) -> bool:
    return (repo / "tools" / "council" / "simulate.py").is_file()
