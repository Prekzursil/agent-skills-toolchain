"""Five class-mix fixtures for IMP-0271 balance arithmetic.

Expected Hamilton numbers are literals, independently computed with
integer largest-remainder arithmetic (not by calling apportion_hamilton):

  Mix hamilton-7: weights (3,3,2,1,1) onto 7 seats, sum_w=10
    floors = (21//10, 21//10, 14//10, 7//10, 7//10) = (2,2,1,0,0)
    remainders = (1,1,4,7,7); leftover=2 → adversary, regulator
    seats = operator=2 end_user=2 domain_expert=1 adversary=1 regulator=1

  Mix hamilton-8-tie: equal weights 1 onto 8 seats, sum_w=5
    floors = 8//5 = 1 each; leftover=3; remainders all 3
    leftover by class-name ascending: adversary, domain_expert, end_user
    seats = adversary=2 domain_expert=2 end_user=2 operator=1 regulator=1
"""

from __future__ import annotations

from typing import Any

CLASSES = (
    "operator",
    "end_user",
    "domain_expert",
    "adversary",
    "regulator",
)


def candidate_pool() -> list[dict[str, str]]:
    """Pool with plenty of every class except regulator (only one)."""
    counts = {
        "operator": 8,
        "end_user": 8,
        "domain_expert": 8,
        "adversary": 8,
        "regulator": 1,
    }
    rows: list[dict[str, str]] = []
    for cls, n in counts.items():
        for i in range(n):
            rows.append(
                {
                    "participant_id": f"{cls}-{i:02d}",
                    "stakeholder_class": cls,
                    "vendor": "fixture",
                    "model": "fixture-model",
                }
            )
    return rows


def mixes() -> list[dict[str, Any]]:
    """Five mixes: three integer targets, two Hamilton, last unfillable."""
    return [
        {
            "id": "equal-integers",
            "kind": "integer-target",
            "fillable": True,
            "target": {
                "operator": 2,
                "end_user": 2,
                "domain_expert": 2,
                "adversary": 2,
                "regulator": 0,
            },
            "expected_seats": {
                "operator": 2,
                "end_user": 2,
                "domain_expert": 2,
                "adversary": 2,
                "regulator": 0,
            },
        },
        {
            "id": "operator-heavy",
            "kind": "integer-target",
            "fillable": True,
            "target": {
                "operator": 4,
                "end_user": 1,
                "domain_expert": 1,
                "adversary": 0,
                "regulator": 0,
            },
            "expected_seats": {
                "operator": 4,
                "end_user": 1,
                "domain_expert": 1,
                "adversary": 0,
                "regulator": 0,
            },
        },
        {
            "id": "hamilton-7",
            "kind": "hamilton",
            "fillable": True,
            "weights": {
                "operator": 3,
                "end_user": 3,
                "domain_expert": 2,
                "adversary": 1,
                "regulator": 1,
            },
            "total_seats": 7,
            "expected_seats": {
                "operator": 2,
                "end_user": 2,
                "domain_expert": 1,
                "adversary": 1,
                "regulator": 1,
            },
        },
        {
            "id": "hamilton-8-tie",
            "kind": "hamilton",
            "fillable": True,
            "weights": {
                "operator": 1,
                "end_user": 1,
                "domain_expert": 1,
                "adversary": 1,
                "regulator": 1,
            },
            "total_seats": 8,
            "expected_seats": {
                "operator": 1,
                "end_user": 2,
                "domain_expert": 2,
                "adversary": 2,
                "regulator": 1,
            },
        },
        {
            "id": "unfillable-regulator",
            "kind": "integer-target",
            "fillable": False,
            "target": {
                "operator": 2,
                "end_user": 2,
                "domain_expert": 2,
                "adversary": 2,
                "regulator": 3,
            },
            "expected_seats": {
                "operator": 2,
                "end_user": 2,
                "domain_expert": 2,
                "adversary": 2,
                "regulator": 1,
            },
            "expected_unfilled": ["regulator"],
            "expected_shortfall": {"regulator": 2},
        },
    ]


def run_mix(select_fn, pool: list[dict[str, str]], mix: dict[str, Any]) -> dict[str, Any]:
    if mix["kind"] == "hamilton":
        return select_fn(
            pool,
            weights=mix["weights"],
            total_seats=mix["total_seats"],
        )
    return select_fn(pool, target=mix["target"])
