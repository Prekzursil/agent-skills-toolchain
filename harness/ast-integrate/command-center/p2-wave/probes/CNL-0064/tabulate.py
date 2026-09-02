"""Weighted tally plus the equal-weight counterfactual (author mechanism).

Every seated ballot is scored twice: once with the declared weights, once with
every seated weight forced to 1. The seated set is frozen (CNL-0058 interface:
the counterfactual must not drop seats or shrink the denominator after the fact).
Non-unit weights require a provenance record (CNL-0023 interface) before any
score is accumulated.
"""
from __future__ import annotations

from collections import defaultdict
from fractions import Fraction
from typing import Any

PROVENANCE_FIELDS = ("basis", "issuer", "issued_at", "evidence_ref")


class Rejected(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}:{detail}")
        self.code = code
        self.detail = detail


def _frac(value: Any) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(value, 1)
    if isinstance(value, float):
        return Fraction(value).limit_denominator(10_000)
    return Fraction(str(value))


def _ballot(seat: dict[str, Any]) -> str | None:
    raw = seat.get("ballot")
    if raw is None:
        return None
    text = str(raw).strip()
    if text == "" or text.upper() == "ABSTAIN":
        return None
    return text


def validate_seats(seats: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    if not seats:
        raise Rejected("EMPTY_COUNCIL", "no seated ballots")
    for seat in seats:
        sid = str(seat.get("id") or "").strip()
        if not sid:
            raise Rejected("MISSING_SEAT_ID", repr(seat))
        if sid in seen:
            raise Rejected("DUPLICATE_SEAT", sid)
        seen.add(sid)
        weight = _frac(seat.get("weight", 1))
        if weight <= 0:
            raise Rejected("NONPOSITIVE_WEIGHT", sid)
        if weight != 1:
            # CNL-0023 interface: a non-unit weight is inert without provenance.
            prov = seat.get("provenance")
            if not isinstance(prov, dict):
                raise Rejected("MISSING_PROVENANCE", sid)
            for field in PROVENANCE_FIELDS:
                if not str(prov.get(field) or "").strip():
                    raise Rejected("INCOMPLETE_PROVENANCE", f"{sid}.{field}")


def _scores(
    seats: list[dict[str, Any]], *, equalize: bool
) -> tuple[dict[str, Fraction], Fraction, int]:
    bucket: dict[str, Fraction] = defaultdict(lambda: Fraction(0))
    seated_weight = Fraction(0)
    seated_count = 0
    for seat in seats:
        weight = Fraction(1, 1) if equalize else _frac(seat.get("weight", 1))
        seated_weight += weight
        seated_count += 1
        choice = _ballot(seat)
        if choice is None:
            continue
        bucket[choice] += weight
    return dict(bucket), seated_weight, seated_count


def _finish(
    scores: dict[str, Fraction],
    seated_weight: Fraction,
    seated_count: int,
    threshold: Fraction | None,
    *,
    equalize: bool,
) -> dict[str, Any]:
    denom = Fraction(seated_count, 1) if equalize else seated_weight
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    if not ranked:
        return {
            "winner": None,
            "status": "NO-BALLOTS",
            "scores": {},
            "denominator": _dump_frac(denom),
            "leading_ratio": _dump_frac(Fraction(0)),
            "seated_count": seated_count,
            "seated_weight": _dump_frac(seated_weight),
        }
    top_opt, top_score = ranked[0]
    tied = [opt for opt, score in ranked if score == top_score]
    ratio = (top_score / denom) if denom else Fraction(0)
    if len(tied) > 1:
        winner: str | None = None
        status = "TIE"
    elif threshold is not None and ratio < threshold:
        winner = None
        status = "THRESHOLD-FAIL"
    elif threshold is not None:
        winner = top_opt
        status = "THRESHOLD-PASS"
    else:
        winner = top_opt
        status = "PLURALITY"
    return {
        "winner": winner,
        "status": status,
        "scores": {opt: _dump_frac(score) for opt, score in ranked},
        "denominator": _dump_frac(denom),
        "leading_ratio": _dump_frac(ratio),
        "seated_count": seated_count,
        "seated_weight": _dump_frac(seated_weight),
    }


def _dump_frac(value: Fraction) -> str:
    value = Fraction(value)
    return f"{value.numerator}/{value.denominator}"


def _parse_frac(text: str) -> Fraction:
    return Fraction(str(text))


def weighting_delta(
    weighted: dict[str, Any],
    equal: dict[str, Any],
    seats: list[dict[str, Any]],
) -> dict[str, Any]:
    """How much of the weighted result is attributable to weight ≠ 1."""
    w_scores = {k: _parse_frac(v) for k, v in (weighted.get("scores") or {}).items()}
    e_scores = {k: _parse_frac(v) for k, v in (equal.get("scores") or {}).items()}
    keys = sorted(set(w_scores) | set(e_scores))
    score_shift = {
        opt: _dump_frac(w_scores.get(opt, Fraction(0)) - e_scores.get(opt, Fraction(0)))
        for opt in keys
    }
    declared_winner = weighted.get("winner")
    excess = Fraction(0)
    if declared_winner:
        for seat in seats:
            if _ballot(seat) != declared_winner:
                continue
            excess += _frac(seat.get("weight", 1)) - Fraction(1, 1)
    dumped = _dump_frac(excess)
    return {
        "score_shift": score_shift,
        "excess_weight_on_weighted_winner": dumped,
        "excess_weight_on_weighted_winner": dumped,
        "winner_changed": weighted.get("winner") != equal.get("winner"),
        "status_changed": weighted.get("status") != equal.get("status"),
    }


def decide(fixture: dict[str, Any]) -> dict[str, Any]:
    """Return a publishable result, or a rejection record."""
    seats = list(fixture.get("seats") or [])
    try:
        validate_seats(seats)
    except Rejected as exc:
        return {
            "id": fixture.get("id"),
            "rejected": True,
            "reject_code": exc.code,
            "reject_detail": exc.detail,
        }
    raw_thr = fixture.get("threshold")
    threshold = None if raw_thr is None else _frac(raw_thr)
    w_scores, w_mass, n = _scores(seats, equalize=False)
    e_scores, e_mass, n2 = _scores(seats, equalize=True)
    assert n == n2
    weighted = _finish(w_scores, w_mass, n, threshold, equalize=False)
    equal = _finish(e_scores, e_mass, n, threshold, equalize=True)
    # Equal-weight counterfactual: every seated ballot is re-scored at weight 1.
    flip = (weighted["winner"] != equal["winner"]) or (
        weighted["status"] != equal["status"]
    )
    delta = weighting_delta(weighted, equal, seats)
    provenance = []
    for seat in seats:
        if _frac(seat.get("weight", 1)) == 1:
            continue
        prov = dict(seat.get("provenance") or {})
        provenance.append({"seat_id": seat["id"], **prov, "weight": str(seat["weight"])})
    return {
        "id": fixture.get("id"),
        "rejected": False,
        "threshold": None if threshold is None else _dump_frac(threshold),
        "weighted_result": weighted,
        "equal_weight_counterfactual": equal,
        "weighting_delta": delta,
        "weighting_flip": bool(flip),
        "provenance": provenance,
        "seated_count": n,
    }
