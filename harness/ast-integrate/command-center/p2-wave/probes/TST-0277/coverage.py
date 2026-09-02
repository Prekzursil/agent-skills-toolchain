"""Exact-id competency coverage. Unknown required ids fail closed."""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from fixtures import TAXONOMY, TRIGGER


def _as_tuple(values: Iterable[str] | None) -> tuple[str, ...]:
    return tuple(str(v) for v in (values or ()))


def coverage_check(
    required: Sequence[str],
    seats: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Map required competencies onto declared seat competencies.

    Coverage is exact id match against TAXONOMY. A seat that declares
    'crypto' does not cover 'cryptography'. Required ids missing from
    TAXONOMY fail closed rather than being silently skipped.
    """
    required_set = set(_as_tuple(required))
    unknown_required = sorted(c for c in required_set if c not in TAXONOMY)
    if unknown_required:
        raise ValueError(
            f"required competencies not in taxonomy: {unknown_required}"
        )

    declared: dict[str, list[str]] = {}
    undeclared_ids: list[str] = []
    for seat in seats:
        sid = str(seat.get("id") or "")
        for raw in _as_tuple(seat.get("competencies")):
            if raw not in TAXONOMY:
                undeclared_ids.append(raw)
                continue
            declared.setdefault(raw, []).append(sid)

    covered = sorted(c for c in required_set if c in declared)
    uncovered = sorted(c for c in required_set if c not in declared)
    fires = bool(uncovered)
    return {
        "required": sorted(required_set),
        "covered": covered,
        "uncovered": uncovered,
        "covered_by": {c: list(declared[c]) for c in covered},
        "undeclared_ids_ignored": sorted(set(undeclared_ids)),
        "fires": fires,
        "trigger": TRIGGER if fires else None,
        "named_gap": list(uncovered),
    }


def recruit(
    uncovered: Sequence[str],
    bench: Sequence[Mapping[str, Any]],
    seated_ids: Iterable[str],
) -> dict[str, Any]:
    """Seat the first unused bench member who declares each uncovered id.

    One recruit may close several remaining gaps. Gaps with no matching
    bench member stay in unfilled.
    """
    seated = set(_as_tuple(seated_ids))
    remaining = [c for c in uncovered]
    recruited: list[dict[str, Any]] = []
    filled: dict[str, str] = {}
    used: set[str] = set()

    for competency in list(uncovered):
        if competency not in remaining:
            continue
        pick = None
        for candidate in bench:
            cid = str(candidate.get("id") or "")
            if not cid or cid in seated or cid in used:
                continue
            comps = set(_as_tuple(candidate.get("competencies")))
            if competency in comps:
                pick = dict(candidate)
                break
        if pick is None:
            continue
        cid = str(pick["id"])
        used.add(cid)
        recruited.append(pick)
        comps = set(_as_tuple(pick.get("competencies")))
        still = []
        for gap in remaining:
            if gap in comps:
                filled[gap] = cid
            else:
                still.append(gap)
        remaining = still

    return {
        "recruited": recruited,
        "filled": filled,
        "unfilled": list(remaining),
        "recruitment_triggered": bool(uncovered),
        "recruitment_executed": bool(recruited),
    }
