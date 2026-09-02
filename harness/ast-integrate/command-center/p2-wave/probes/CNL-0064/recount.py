"""Independent recount: group ballots by option, then sum (reviewer mechanism).

Does not import tabulate. Uses grouped lists rather than a running accumulator so
a disagreement in the number is a real disagreement, not a shared helper echoing
itself.
"""
from __future__ import annotations

from fractions import Fraction
from typing import Any

NEED_PROV = ("basis", "issuer", "issued_at", "evidence_ref")


class RecountReject(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}:{detail}")
        self.code = code
        self.detail = detail


def _q(value: Any) -> Fraction:
    return Fraction(str(value))


def _choice(seat: dict[str, Any]) -> str | None:
    raw = seat.get("ballot")
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text.upper() == "ABSTAIN":
        return None
    return text


def _check(seats: list[dict[str, Any]]) -> None:
    names: list[str] = []
    if not seats:
        raise RecountReject("EMPTY_COUNCIL", "no seated ballots")
    for seat in seats:
        name = str(seat.get("id") or "").strip()
        if not name:
            raise RecountReject("MISSING_SEAT_ID", "blank")
        if name in names:
            raise RecountReject("DUPLICATE_SEAT", name)
        names.append(name)
        w = _q(seat.get("weight", 1))
        if w <= 0:
            raise RecountReject("NONPOSITIVE_WEIGHT", name)
        if w != 1:
            rec = seat.get("provenance")
            if not isinstance(rec, dict):
                raise RecountReject("MISSING_PROVENANCE", name)
            for key in NEED_PROV:
                if not str(rec.get(key) or "").strip():
                    raise RecountReject("INCOMPLETE_PROVENANCE", f"{name}.{key}")


def _groups(seats: list[dict[str, Any]]) -> tuple[dict[str, list[Fraction]], int]:
    """Map option -> list of contributing weights (not a running total)."""
    grouped: dict[str, list[Fraction]] = {}
    for seat in seats:
        opt = _choice(seat)
        if opt is None:
            continue
        grouped.setdefault(opt, []).append(_q(seat.get("weight", 1)))
    return grouped, len(seats)


def _sum_list(parts: list[Fraction]) -> Fraction:
    total = Fraction(0)
    for part in parts:
        total += part
    return total


def _outcome(
    grouped_weights: dict[str, list[Fraction]],
    seated_n: int,
    seated_w: Fraction,
    threshold: Fraction | None,
    *,
    equal: bool,
) -> dict[str, Any]:
    if equal:
        scores = {opt: Fraction(len(parts), 1) for opt, parts in grouped_weights.items()}
        denom = Fraction(seated_n, 1)
    else:
        scores = {opt: _sum_list(parts) for opt, parts in grouped_weights.items()}
        denom = seated_w
    order = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    dump = {k: f"{v.numerator}/{v.denominator}" for k, v in order}
    if not order:
        return {
            "winner": None,
            "status": "NO-BALLOTS",
            "scores": {},
            "denominator": f"{denom.numerator}/{denom.denominator}",
        }
    lead_opt, lead_sc = order[0]
    peers = [k for k, v in order if v == lead_sc]
    ratio = (lead_sc / denom) if denom else Fraction(0)
    if len(peers) > 1:
        winner = None
        status = "TIE"
    elif threshold is not None and ratio < threshold:
        winner = None
        status = "THRESHOLD-FAIL"
    elif threshold is not None:
        winner = lead_opt
        status = "THRESHOLD-PASS"
    else:
        winner = lead_opt
        status = "PLURALITY"
    return {
        "winner": winner,
        "status": status,
        "scores": dump,
        "denominator": f"{denom.numerator}/{denom.denominator}",
        "leading_ratio": f"{ratio.numerator}/{ratio.denominator}",
    }


def recount(fixture: dict[str, Any]) -> dict[str, Any]:
    seats = list(fixture.get("seats") or [])
    try:
        _check(seats)
    except RecountReject as exc:
        return {
            "id": fixture.get("id"),
            "rejected": True,
            "reject_code": exc.code,
            "reject_detail": exc.detail,
        }
    grouped, n = _groups(seats)
    seated_w = _sum_list([_q(s.get("weight", 1)) for s in seats])
    thr_raw = fixture.get("threshold")
    thr = None if thr_raw is None else _q(thr_raw)
    weighted = _outcome(grouped, n, seated_w, thr, equal=False)
    equalized = _outcome(grouped, n, seated_w, thr, equal=True)
    flip = (weighted["winner"] != equalized["winner"]) or (
        weighted["status"] != equalized["status"]
    )
    return {
        "id": fixture.get("id"),
        "rejected": False,
        "weighted_winner": weighted["winner"],
        "weighted_status": weighted["status"],
        "weighted_scores": weighted["scores"],
        "equal_winner": equalized["winner"],
        "equal_status": equalized["status"],
        "equal_scores": equalized["scores"],
        "weighting_flip": bool(flip),
        "seated_count": n,
    }
