"""Decision-versus-N sensitivity sweep for council questions (IMP-0367).

For a question with an ordered seat list, the production path recomputes the
majority decision on every prefix N = 1..len(seats) and *publishes that whole
curve*.  From the curve it derives the stabilisation point N* (the first N
from which the decision never changes again), whether the question is
N-sensitive at all, and how the configured default seat count relates to N*.
Nothing on the production path tunes N to make the curve look stable.

``tune_until_stable`` exists only as the negative control: it drops the
unstable head of a curve until one decision remains, which is exactly the
move the production path must never make.  ``AGG_N_MODULATED`` is a
deliberately N-dependent aggregator (even panels are called TIE regardless of
ballots) so the sweep can be shown to *report* protocol-induced N-sensitivity
rather than hide it.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Sequence

SPEC_ANCHOR = "WORK-UNIT-CATALOG.json:IMP-0367 question_or_target; _USER-PROMPTS.md:10915-10946"

AGG_MAJORITY = "majority"
AGG_N_MODULATED = "n-modulated"
AGGREGATORS: tuple[str, ...] = (AGG_MAJORITY, AGG_N_MODULATED)

DEFAULT_SEAT_COUNT = 5
LOW_N_MAX = 2

TIE = "TIE"
NO_QUORUM = "NO-QUORUM"

FINDING_NOT_TUNED = "protocol-n-sensitive-not-tuned"
FINDING_WAS_TUNED = "protocol-n-sensitive-WAS-TUNED"
FINDING_CURVE_TUNED = "curve-WAS-TUNED"


class SensitivityError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def load_question(path: str | Path) -> dict[str, Any]:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or not isinstance(doc.get("seats"), list):
        raise SensitivityError(f"{path}: question needs a 'seats' list")
    for i, seat in enumerate(doc["seats"]):
        if not isinstance(seat, dict) or "vote" not in seat:
            raise SensitivityError(f"{path}: seat {i} has no 'vote'")
    doc.setdefault("id", Path(path).stem)
    doc.setdefault("default_n", DEFAULT_SEAT_COUNT)
    return doc


def seat_votes(question: dict[str, Any]) -> list[str]:
    return [str(seat["vote"]) for seat in question["seats"]]


# ---------------------------------------------------------------------------
# Aggregators
# ---------------------------------------------------------------------------


def tally(votes: Sequence[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for vote in votes:
        counts[vote] = counts.get(vote, 0) + 1
    return dict(sorted(counts.items()))


def aggregate_majority(votes: Sequence[str]) -> str:
    """Plurality winner; TIE when the top count is shared; NO-QUORUM when empty."""
    if not votes:
        return NO_QUORUM
    counts = tally(votes)
    top = max(counts.values())
    winners = [k for k, n in counts.items() if n == top]
    return winners[0] if len(winners) == 1 else TIE


def aggregate_n_modulated(votes: Sequence[str]) -> str:
    """Mutant protocol whose answer depends on N itself: even panels are TIE."""
    if not votes:
        return NO_QUORUM
    if len(votes) % 2 == 0:
        return TIE
    return aggregate_majority(votes)


AGGREGATOR_FUNCS: dict[str, Callable[[Sequence[str]], str]] = {
    AGG_MAJORITY: aggregate_majority,
    AGG_N_MODULATED: aggregate_n_modulated,
}


def _aggregator(name: str) -> Callable[[Sequence[str]], str]:
    try:
        return AGGREGATOR_FUNCS[name]
    except KeyError:
        raise SensitivityError(f"unknown aggregator {name!r}; expected one of {AGGREGATORS}") from None


# ---------------------------------------------------------------------------
# Curve, stabilisation, and the tuning control
# ---------------------------------------------------------------------------


def decision_curve(question: dict[str, Any], aggregator: str = AGG_MAJORITY) -> list[dict[str, Any]]:
    """Decision on every prefix N = 1..len(seats), in seat order."""
    agg = _aggregator(aggregator)
    votes = seat_votes(question)
    curve: list[dict[str, Any]] = []
    for n in range(1, len(votes) + 1):
        prefix = votes[:n]
        curve.append({"n": n, "decision": agg(prefix), "tally": tally(prefix)})
    return curve


def stabilisation(curve: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """N* = first N from which the decision never changes again."""
    if not curve:
        raise SensitivityError("cannot stabilise an empty curve")
    decisions = [p["decision"] for p in curve]
    distinct: list[str] = []
    for d in decisions:
        if d not in distinct:
            distinct.append(d)
    star_i = len(curve) - 1
    for i in range(len(decisions)):
        if all(d == decisions[i] for d in decisions[i:]):
            star_i = i
            break
    tail = len(curve) - star_i
    n_sensitive = len(distinct) > 1
    flips = sum(1 for a, b in zip(decisions, decisions[1:]) if a != b)
    return {
        "stabilisation_n": int(curve[star_i]["n"]),
        "stable_decision": decisions[star_i],
        "trivial_stabilisation": n_sensitive and tail == 1,
        "n_sensitive": n_sensitive,
        "distinct_decisions": distinct,
        "flip_count": flips,
        "points": len(curve),
    }


def tune_until_stable(curve: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """NEGATIVE CONTROL ONLY: drop the unstable head until one decision is left.

    This is the forbidden move.  It always returns a curve with a single
    distinct decision (the stable tail), discarding the flips that the
    production path is required to publish.
    """
    points = [dict(p) for p in curve]
    while len({p["decision"] for p in points}) > 1:
        points.pop(0)
    return points


# ---------------------------------------------------------------------------
# Production evaluation
# ---------------------------------------------------------------------------


def _decision_at(curve: Sequence[dict[str, Any]], n: int) -> str:
    if not curve:
        return NO_QUORUM
    for point in curve:
        if int(point["n"]) == n:
            return str(point["decision"])
    if n < int(curve[0]["n"]):
        return NO_QUORUM
    return str(curve[-1]["decision"])


def evaluate_question(
    question: dict[str, Any],
    aggregator: str = AGG_MAJORITY,
    retune: bool = False,
) -> dict[str, Any]:
    """Publish the decision-versus-N curve and compare N* with the default.

    ``retune=True`` is not a production setting: it runs the curve through
    ``tune_until_stable`` and says so in ``retuned`` / ``finding``.
    """
    curve = decision_curve(question, aggregator)
    majority_curve = curve if aggregator == AGG_MAJORITY else decision_curve(question, AGG_MAJORITY)
    stab = stabilisation(curve)
    # Protocol-induced N-sensitivity: the aggregator's curve disagrees with the
    # plain majority of the same ballots, so the N-dependence is the protocol's.
    protocol_is_n_sensitive = [p["decision"] for p in curve] != [p["decision"] for p in majority_curve]

    published = tune_until_stable(curve) if retune else [dict(p) for p in curve]
    retuned = bool(retune)
    if retuned and protocol_is_n_sensitive:
        finding: str | None = FINDING_WAS_TUNED
    elif retuned:
        finding = FINDING_CURVE_TUNED
    elif protocol_is_n_sensitive:
        finding = FINDING_NOT_TUNED
    else:
        finding = None

    default_n = int(question.get("default_n", DEFAULT_SEAT_COUNT))
    n_star = int(stab["stabilisation_n"])
    if default_n > n_star:
        relation = "above"
    elif default_n == n_star:
        relation = "at"
    else:
        relation = "below"
    default_decision = _decision_at(curve, default_n)
    evidence = question.get("evidence") or {}
    return {
        "question_id": str(question.get("id")),
        "question_class": question.get("class"),
        "aggregator": aggregator,
        "seat_count": len(question["seats"]),
        "curve": [dict(p) for p in curve],
        "published_curve": published,
        "stabilisation": stab,
        "default_n": default_n,
        "default_decision": default_decision,
        "default_relation": relation,
        "default_would_emit_unstable_answer": default_decision != stab["stable_decision"],
        "low_n_stable": n_star <= LOW_N_MAX,
        "protocol_is_n_sensitive": protocol_is_n_sensitive,
        "evidence_decisive": bool(evidence.get("decisive")),
        "evidence_answer": evidence.get("answer"),
        "stable_matches_evidence": (
            evidence.get("answer") == stab["stable_decision"] if evidence.get("decisive") else None
        ),
        "retuned": retuned,
        "finding": finding,
        "production_path": aggregator == AGG_MAJORITY and not retuned,
    }


def public_row(result: dict[str, Any]) -> dict[str, Any]:
    """The receipt-facing row: curve points as (n, decision) plus the verdicts."""
    stab = result["stabilisation"]
    return {
        "question_id": result["question_id"],
        "question_class": result["question_class"],
        "aggregator": result["aggregator"],
        "curve": [{"n": int(p["n"]), "decision": p["decision"]} for p in result["published_curve"]],
        "stabilisation_n": int(stab["stabilisation_n"]),
        "stable_decision": stab["stable_decision"],
        "trivial_stabilisation": bool(stab["trivial_stabilisation"]),
        "n_sensitive": bool(stab["n_sensitive"]),
        "distinct_decisions": list(stab["distinct_decisions"]),
        "flip_count": int(stab["flip_count"]),
        "default_n": int(result["default_n"]),
        "default_decision": result["default_decision"],
        "default_relation": result["default_relation"],
        "default_would_emit_unstable_answer": bool(result["default_would_emit_unstable_answer"]),
        "low_n_stable": bool(result["low_n_stable"]),
        "protocol_is_n_sensitive": bool(result["protocol_is_n_sensitive"]),
        "retuned": bool(result["retuned"]),
        "finding": result["finding"],
        "production_path": bool(result["production_path"]),
    }


__all__ = [
    "AGGREGATORS",
    "AGGREGATOR_FUNCS",
    "AGG_MAJORITY",
    "AGG_N_MODULATED",
    "DEFAULT_SEAT_COUNT",
    "FINDING_CURVE_TUNED",
    "FINDING_NOT_TUNED",
    "FINDING_WAS_TUNED",
    "LOW_N_MAX",
    "NO_QUORUM",
    "SPEC_ANCHOR",
    "SensitivityError",
    "TIE",
    "aggregate_majority",
    "aggregate_n_modulated",
    "decision_curve",
    "evaluate_question",
    "load_question",
    "public_row",
    "seat_votes",
    "stabilisation",
    "tally",
    "tune_until_stable",
]
