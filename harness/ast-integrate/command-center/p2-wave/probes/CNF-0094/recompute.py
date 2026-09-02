#!/usr/bin/env python3
"""Independent recompute of council calibration from raw per-round ballots.

The published report is never an input to the scorer. Only raw votes,
stated confidences, weights, abstentions and delegations are.

Arithmetic is exact (fractions.Fraction). Floats are emission-only.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable

# Quoted aggregation rule — an undeclared rule is a specification gap (CNF-0094).
DECLARED_AGGREGATION_RULE = (
    "ABSTENTION: a ballot with choice=abstain is excluded from the Brier "
    "denominator and from weighted accuracy; it increments abstention_count "
    "and keeps its raw weight in the abstention bucket. It does not add "
    "weight to any option. "
    "DELEGATION: a ballot with choice=delegate transfers its entire raw "
    "weight to the named seat in the same round. The delegator's stated "
    "confidence is not an independently scored prediction. Weight follows "
    "the chain to a terminal aye/nay/abstain ballot. A cycle or a missing "
    "target excludes that weight (cycle_or_unresolved_weight) rather than "
    "silently dropping it. If the terminal abstains, the whole incoming "
    "chain is counted as abstention, not as a scored prediction. "
    "WEIGHTS: the Brier score is sum_i w_i*(p_i-o_i)^2 / sum_i w_i over "
    "scored (non-abstain, non-delegator, non-excluded) terminals, where "
    "p_i is the terminal's stated confidence in its own choice and o_i is "
    "1 if that choice equals the round's resolved_outcome else 0. Treating "
    "every scored ballot as w_i=1 when any raw w_i!=1 is the arithmetic "
    "error 'a weighted vote counted as unweighted'."
)
RULE_SOURCE = "command-center/p2-wave/probes/CNF-0094/recompute.py:DECLARED_AGGREGATION_RULE"

AYE_NAY = frozenset({"aye", "nay"})
TERMINAL = frozenset({"aye", "nay", "abstain"})


def F(value: Any) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, float):
        return Fraction(str(value))
    if isinstance(value, str):
        if "/" in value and value.count("/") == 1:
            a, b = value.split("/")
            return Fraction(int(a.strip()), int(b.strip()))
        return Fraction(value)
    raise TypeError(f"cannot coerce {type(value)!r} to Fraction")


def fnum(x: Fraction) -> float:
    return float(x)


@dataclass
class ScoredBallot:
    round_id: str
    seat: str
    choice: str
    p: Fraction
    weight: Fraction
    outcome: int
    resolved: str
    source_seats: list[str]


@dataclass
class RoundStats:
    round_id: str
    resolved: str
    scored: list[ScoredBallot] = field(default_factory=list)
    abstention_count: int = 0
    abstention_weight: Fraction = Fraction(0)
    delegated_count: int = 0
    delegated_weight: Fraction = Fraction(0)
    excluded_count: int = 0
    excluded_weight: Fraction = Fraction(0)
    raw_weight: Fraction = Fraction(0)


@dataclass
class Scores:
    brier_weighted: Fraction
    brier_unweighted: Fraction
    weighted_accuracy: Fraction
    mean_confidence_weighted: Fraction
    scored_n: int
    scored_weight: Fraction
    abstention_count: int
    abstention_weight: Fraction
    delegated_count: int
    delegated_weight: Fraction
    excluded_count: int
    excluded_weight: Fraction
    raw_weight: Fraction
    weight_conserved: bool
    scored: list[ScoredBallot]
    rounds: list[RoundStats]

    def as_jsonable(self) -> dict[str, Any]:
        return {
            "brier_weighted": fnum(self.brier_weighted),
            "brier_weighted_fraction": str(self.brier_weighted),
            "brier_unweighted": fnum(self.brier_unweighted),
            "brier_unweighted_fraction": str(self.brier_unweighted),
            "weighted_accuracy": fnum(self.weighted_accuracy),
            "weighted_accuracy_fraction": str(self.weighted_accuracy),
            "mean_confidence_weighted": fnum(self.mean_confidence_weighted),
            "mean_confidence_weighted_fraction": str(self.mean_confidence_weighted),
            "scored_n": self.scored_n,
            "scored_weight": fnum(self.scored_weight),
            "scored_weight_fraction": str(self.scored_weight),
            "abstention_count": self.abstention_count,
            "abstention_weight": fnum(self.abstention_weight),
            "delegated_count": self.delegated_count,
            "delegated_weight": fnum(self.delegated_weight),
            "excluded_count": self.excluded_count,
            "excluded_weight": fnum(self.excluded_weight),
            "raw_weight": fnum(self.raw_weight),
            "weight_conserved": self.weight_conserved,
        }


def _follow(
    seat: str,
    by_seat: dict[str, dict[str, Any]],
    stack: tuple[str, ...],
) -> tuple[str, str, tuple[str, ...]]:
    """Return (status, terminal_or_reason, chain) status in terminal|cycle|missing|invalid."""
    if seat in stack:
        return "cycle", seat, stack + (seat,)
    ballot = by_seat.get(seat)
    if ballot is None:
        return "missing", seat, stack
    choice = str(ballot.get("choice") or "")
    if choice in TERMINAL:
        return "terminal", seat, stack + (seat,)
    if choice == "delegate":
        target = str(ballot.get("delegate_to") or "")
        if not target:
            return "missing", seat, stack + (seat,)
        return _follow(target, by_seat, stack + (seat,))
    return "invalid", seat, stack + (seat,)


def resolve_round(round_doc: dict[str, Any]) -> RoundStats:
    round_id = str(round_doc.get("round_id") or round_doc.get("id") or "")
    resolved = str(round_doc.get("resolved_outcome") or "")
    ballots = list(round_doc.get("ballots") or [])
    stats = RoundStats(round_id=round_id, resolved=resolved)
    by_seat: dict[str, dict[str, Any]] = {}
    for ballot in ballots:
        seat = str(ballot.get("seat") or "")
        if not seat or seat in by_seat:
            raise ValueError(f"round {round_id}: duplicate or empty seat {seat!r}")
        by_seat[seat] = ballot
        stats.raw_weight += F(ballot.get("weight", 1))

    incoming: dict[str, list[str]] = {seat: [] for seat in by_seat}
    landing: dict[str, str] = {}
    excluded: dict[str, str] = {}

    for seat, ballot in by_seat.items():
        status, term, chain = _follow(seat, by_seat, ())
        if status != "terminal":
            excluded[seat] = status
            continue
        landing[seat] = term
        if seat != term:
            incoming[term].append(seat)

    scored_seats: set[str] = set()
    for seat, ballot in by_seat.items():
        if seat in excluded:
            stats.excluded_count += 1
            stats.excluded_weight += F(ballot.get("weight", 1))
            continue
        term = landing[seat]
        term_b = by_seat[term]
        term_choice = str(term_b.get("choice") or "")
        if str(ballot.get("choice") or "") == "delegate":
            stats.delegated_count += 1
            stats.delegated_weight += F(ballot.get("weight", 1))
        if term_choice == "abstain":
            if seat == term:
                stats.abstention_count += 1
            stats.abstention_weight += F(ballot.get("weight", 1))
            continue
        if term_choice not in AYE_NAY:
            stats.excluded_count += 1
            stats.excluded_weight += F(ballot.get("weight", 1))
            continue
        if term in scored_seats:
            continue
        scored_seats.add(term)
        chain = [term] + incoming[term]
        weight = sum((F(by_seat[s].get("weight", 1)) for s in chain), Fraction(0))
        p = F(term_b.get("confidence") if "confidence" in term_b else term_b.get("p"))
        outcome = 1 if term_choice == resolved else 0
        stats.scored.append(
            ScoredBallot(
                round_id=round_id,
                seat=term,
                choice=term_choice,
                p=p,
                weight=weight,
                outcome=outcome,
                resolved=resolved,
                source_seats=chain,
            )
        )
    return stats


def _safe_div(num: Fraction, den: Fraction) -> Fraction:
    if den == 0:
        return Fraction(0)
    return num / den


def score_rounds(rounds: Iterable[dict[str, Any]]) -> Scores:
    round_stats = [resolve_round(r) for r in rounds]
    scored: list[ScoredBallot] = []
    for rs in round_stats:
        scored.extend(rs.scored)

    w_err = sum((b.weight * (b.p - b.outcome) ** 2 for b in scored), Fraction(0))
    w_sum = sum((b.weight for b in scored), Fraction(0))
    u_err = sum(((b.p - b.outcome) ** 2 for b in scored), Fraction(0))
    acc_w = sum((b.weight for b in scored if b.outcome == 1), Fraction(0))
    mean_p = sum((b.weight * b.p for b in scored), Fraction(0))

    abst_n = sum(rs.abstention_count for rs in round_stats)
    abst_w = sum((rs.abstention_weight for rs in round_stats), Fraction(0))
    del_n = sum(rs.delegated_count for rs in round_stats)
    del_w = sum((rs.delegated_weight for rs in round_stats), Fraction(0))
    exc_n = sum(rs.excluded_count for rs in round_stats)
    exc_w = sum((rs.excluded_weight for rs in round_stats), Fraction(0))
    raw_w = sum((rs.raw_weight for rs in round_stats), Fraction(0))
    conserved = (w_sum + abst_w + exc_w) == raw_w

    return Scores(
        brier_weighted=_safe_div(w_err, w_sum),
        brier_unweighted=_safe_div(u_err, Fraction(len(scored))) if scored else Fraction(0),
        weighted_accuracy=_safe_div(acc_w, w_sum),
        mean_confidence_weighted=_safe_div(mean_p, w_sum),
        scored_n=len(scored),
        scored_weight=w_sum,
        abstention_count=abst_n,
        abstention_weight=abst_w,
        delegated_count=del_n,
        delegated_weight=del_w,
        excluded_count=exc_n,
        excluded_weight=exc_w,
        raw_weight=raw_w,
        weight_conserved=conserved,
        scored=scored,
        rounds=round_stats,
    )


def load_run(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def score_run(run: dict[str, Any]) -> Scores:
    rounds = run.get("rounds")
    if not isinstance(rounds, list) or not rounds:
        raise ValueError("run has no rounds")
    return score_rounds(rounds)


def compare_to_hand(scores: Scores, expected: dict[str, Any]) -> dict[str, Any]:
    fields = [
        "brier_weighted",
        "brier_unweighted",
        "weighted_accuracy",
        "mean_confidence_weighted",
        "scored_n",
        "scored_weight",
        "abstention_count",
        "delegated_count",
        "delegated_weight",
    ]
    rows = []
    matched = True
    for field in fields:
        rec = getattr(scores, field)
        exp_raw = expected[field]
        if field.endswith("_count") or field == "scored_n":
            rec_f = int(rec)
            exp_f = int(exp_raw)
            ok = rec_f == exp_f
            rows.append(
                {
                    "field": field,
                    "hand_computed": exp_f,
                    "recomputed": rec_f,
                    "match": ok,
                }
            )
        else:
            rec_f = rec if isinstance(rec, Fraction) else F(rec)
            exp_f = F(exp_raw)
            ok = rec_f == exp_f
            rows.append(
                {
                    "field": field,
                    "hand_computed": str(exp_f),
                    "hand_computed_float": fnum(exp_f),
                    "recomputed": str(rec_f),
                    "recomputed_float": fnum(rec_f),
                    "match": ok,
                }
            )
        if not ok:
            matched = False
    return {"matched": matched, "rows": rows}


def weighted_counted_as_unweighted(scores: Scores, published_brier: Any) -> dict[str, Any]:
    """Hunt: published Brier equals unweighted while weights are non-uniform."""
    pub = F(published_brier)
    weights_vary = any(b.weight != 1 for b in scores.scored) or len({b.weight for b in scores.scored}) > 1
    equals_unweighted = pub == scores.brier_unweighted
    equals_weighted = pub == scores.brier_weighted
    distinct = scores.brier_weighted != scores.brier_unweighted
    fired = bool(weights_vary and distinct and equals_unweighted and not equals_weighted)
    return {
        "fired": fired,
        "weights_vary": weights_vary,
        "weighted_differs_from_unweighted": distinct,
        "published_equals_unweighted": equals_unweighted,
        "published_equals_weighted": equals_weighted,
        "published_brier": str(pub),
        "recomputed_weighted": str(scores.brier_weighted),
        "recomputed_unweighted": str(scores.brier_unweighted),
        "classification": "arithmetic-error" if fired else "not-this-error",
    }


def _published_rule_quote(published: dict[str, Any]) -> str:
    quote: Any = published.get("aggregation_rule_quote") or published.get("aggregation_rule")
    agg = published.get("aggregation")
    if not quote and isinstance(agg, dict):
        quote = agg.get("rule") or agg.get("quoted") or agg.get("text")
    if isinstance(quote, dict):
        quote = quote.get("quoted") or quote.get("text")
    return str(quote or "").strip()


def undeclared_rule(published: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(published, dict):
        return {
            "undeclared": True,
            "classification": "undeclared-aggregation-rule",
            "reason": "no published report object to quote a rule from",
        }
    text = _published_rule_quote(published)
    if len(text) < 40:
        return {
            "undeclared": True,
            "classification": "undeclared-aggregation-rule",
            "reason": "published report does not quote an abstention/weight/delegation rule of >=40 chars",
            "quote_len": len(text),
        }
    return {"undeclared": False, "classification": None, "quote": text}


def function_line(path: Path, needle: str) -> int:
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines, 1):
        if needle in line:
            return i
    return 1


def reliability_bins(scores: Scores) -> list[dict[str, Any]]:
    edges = [
        (Fraction(0), Fraction("0.6"), "[0.0,0.6)"),
        (Fraction("0.6"), Fraction("0.8"), "[0.6,0.8)"),
        (Fraction("0.8"), Fraction(2), "[0.8,1.0]"),
    ]
    out = []
    for lo, hi, label in edges:
        if hi == Fraction(2):
            bucket = [b for b in scores.scored if b.p >= lo]
        else:
            bucket = [b for b in scores.scored if b.p >= lo and b.p < hi]
        n_w = sum((b.weight for b in bucket), Fraction(0))
        if n_w == 0:
            out.append(
                {
                    "bin": label,
                    "n": 0,
                    "mean_predicted": 0.0,
                    "observed_rate": 0.0,
                }
            )
            continue
        mean_p = sum((b.weight * b.p for b in bucket), Fraction(0)) / n_w
        obs = sum((b.weight * b.outcome for b in bucket), Fraction(0)) / n_w
        out.append(
            {
                "bin": label,
                "n": fnum(n_w),
                "n_fraction": str(n_w),
                "mean_predicted": fnum(mean_p),
                "observed_rate": fnum(obs),
            }
        )
    return out
