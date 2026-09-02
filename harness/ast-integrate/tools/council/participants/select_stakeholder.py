"""Stakeholder-balanced council selector (IMP-0271)."""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

STAKEHOLDER_CLASSES = (
    "operator",
    "end_user",
    "domain_expert",
    "adversary",
    "regulator",
)
REASON_SUPPRESSED = "UNFILLED_REPORT_SUPPRESSED"
REASON_OK = "ok"


def apportion_hamilton(weights: Mapping[str, int], total_seats: int) -> dict[str, int]:
    """Largest-remainder (Hamilton) apportionment. Ties break by class-name ASC."""
    classes = list(STAKEHOLDER_CLASSES)
    w = {c: int(weights.get(c, 0)) for c in classes}
    sum_w = sum(w.values()) or 1
    floors = {c: (w[c] * total_seats) // sum_w for c in classes}
    remainders = {c: (w[c] * total_seats) % sum_w for c in classes}
    leftover = total_seats - sum(floors.values())
    order = sorted(classes, key=lambda c: (-remainders[c], c))
    seats = dict(floors)
    for c in order[:leftover]:
        seats[c] += 1
    return seats


def _empty_census() -> dict[str, int]:
    return {c: 0 for c in STAKEHOLDER_CLASSES}


def _take_seats(pool: list[dict[str, str]], requested: Mapping[str, int]) -> dict[str, Any]:
    remaining = list(pool)
    seats: list[dict[str, str]] = []
    unfilled: list[dict[str, Any]] = []
    for cls in STAKEHOLDER_CLASSES:
        want = int(requested.get(cls, 0) or 0)
        got = 0
        kept: list[dict[str, str]] = []
        for row in remaining:
            if got < want and row.get("stakeholder_class") == cls:
                seats.append(dict(row))
                got += 1
            else:
                kept.append(row)
        remaining = kept
        if got < want:
            unfilled.append(
                {
                    "stakeholder_class": cls,
                    "requested": want,
                    "seated": got,
                    "shortfall": want - got,
                }
            )
    census = _empty_census()
    for s in seats:
        census[str(s["stakeholder_class"])] += 1
    requested_balance = {c: int(requested.get(c, 0) or 0) for c in STAKEHOLDER_CLASSES}
    under = bool(unfilled)
    return {
        "seats": seats,
        "roster": list(seats),
        "census": census,
        "requested_balance": requested_balance,
        "unfilled_report": unfilled,
        "unfilled_report_emitted": True,
        "under_represented": under,
        "ok": True,
    }


def select(
    pool: list[dict[str, str]],
    *,
    target: Mapping[str, int] | None = None,
    weights: Mapping[str, int] | None = None,
    total_seats: int | None = None,
) -> dict[str, Any]:
    if weights is not None:
        if total_seats is None:
            raise ValueError("total_seats required with weights")
        requested = apportion_hamilton(weights, int(total_seats))
    elif target is not None:
        requested = {c: int(target.get(c, 0) or 0) for c in STAKEHOLDER_CLASSES}
    else:
        raise ValueError("select requires target= or weights=")
    return _take_seats(pool, requested)


def census_check(run: Mapping[str, Any]) -> dict[str, Any]:
    requested = run.get("requested_balance") or {}
    census = run.get("census")
    if not isinstance(census, dict):
        seats = run.get("seats") or []
        census = Counter(str(s.get("stakeholder_class")) for s in seats)
    short: list[str] = []
    for cls in STAKEHOLDER_CLASSES:
        want = int(requested.get(cls, 0) or 0)
        got = int(census.get(cls, 0) or 0)
        if got < want:
            short.append(cls)
    report = run.get("unfilled_report", "__missing__")
    if short:
        if report in (None, "__missing__") or report == []:
            return {"ok": False, "reason": REASON_SUPPRESSED, "short": short}
        names = [r.get("stakeholder_class") for r in report if isinstance(r, dict)]
        if sorted(names) != sorted(short):
            return {"ok": False, "reason": REASON_SUPPRESSED, "short": short}
        return {"ok": True, "reason": REASON_OK, "short": short}
    return {"ok": True, "reason": REASON_OK, "short": []}
