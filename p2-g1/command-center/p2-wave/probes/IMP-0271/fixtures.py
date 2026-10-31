"""IMP-0271 probe fixtures: five stakeholder mixes with hand-computed targets.

MIX-1 balanced target, every class fillable.
MIX-2 Hamilton largest-remainder with a leftover seat and an alphabetical
     tie between operator and end_user (end_user wins, name ASC).
MIX-3 Hamilton tie on remainders between adversary and regulator, both plus
     one (name ASC order: adversary before regulator).
MIX-4 unfillable regulator: 3 requested, 1 available -> shortfall must be
     reported, not silently absorbed.
MIX-5 even weights, zero leftover, exact split.
"""
from __future__ import annotations

CLASSES = ("operator", "end_user", "domain_expert", "adversary", "regulator")


def _rows(prefix: str, counts: dict[str, int]) -> list[dict[str, str]]:
    out = []
    for cls, n in counts.items():
        for i in range(n):
            out.append({"participant_id": f"{prefix}-{cls}-{i}", "stakeholder_class": cls})
    return out


MIXES = [
    {
        "id": "MIX-1-balanced-target",
        "pool": _rows("m1", {"operator": 3, "end_user": 3, "domain_expert": 2, "adversary": 1, "regulator": 1}),
        "select": {"target": {"operator": 2, "end_user": 2, "domain_expert": 1, "adversary": 1}},
        "expected_seats": {"operator": 2, "end_user": 2, "domain_expert": 1, "adversary": 1, "regulator": 0},
        "expected_unfilled": [],
    },
    {
        "id": "MIX-2-hamilton-leftover-alpha-tie",
        "pool": _rows("m2", {"operator": 4, "end_user": 4, "domain_expert": 2}),
        "select": {"weights": {"operator": 50, "end_user": 30, "domain_expert": 20}, "total_seats": 5},
        "expected_seats": {"operator": 2, "end_user": 2, "domain_expert": 1, "adversary": 0, "regulator": 0},
        "expected_unfilled": [],
    },
    {
        "id": "MIX-3-hamilton-double-tie",
        "pool": _rows("m3", {"domain_expert": 6, "adversary": 2, "regulator": 2}),
        "select": {"weights": {"domain_expert": 80, "adversary": 10, "regulator": 10}, "total_seats": 7},
        "expected_seats": {"operator": 0, "end_user": 0, "domain_expert": 5, "adversary": 1, "regulator": 1},
        "expected_unfilled": [],
    },
    {
        "id": "MIX-4-unfillable-regulator",
        "pool": _rows("m4", {"operator": 3, "regulator": 1}),
        "select": {"target": {"operator": 1, "regulator": 3}},
        "expected_seats": {"operator": 1, "end_user": 0, "domain_expert": 0, "adversary": 0, "regulator": 1},
        "expected_unfilled": [{"stakeholder_class": "regulator", "requested": 3, "seated": 1, "shortfall": 2}],
    },
    {
        "id": "MIX-5-even-weights-exact",
        "pool": _rows("m5", {"operator": 2, "end_user": 2, "domain_expert": 2, "adversary": 2, "regulator": 2}),
        "select": {"weights": {"operator": 10, "end_user": 10, "domain_expert": 10, "adversary": 10, "regulator": 10}, "total_seats": 5},
        "expected_seats": {"operator": 1, "end_user": 1, "domain_expert": 1, "adversary": 1, "regulator": 1},
        "expected_unfilled": [],
    },
]
