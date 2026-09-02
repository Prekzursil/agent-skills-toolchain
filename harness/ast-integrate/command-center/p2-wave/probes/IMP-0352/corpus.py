"""Hermetic 20-council corpus and ceiling fixtures for IMP-0352."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.council.budget.preflight import (  # noqa: E402
    Cost,
    CouncilPlan,
    OwnerCeiling,
    estimate_cost,
)

# actual/estimate factors. Nearest-rank p90 of (factor-1) for n=20 is
# the 18th sorted value (ceil(0.9*20)=18).
TOKEN_FACTORS: tuple[float, ...] = (
    0.80, 0.82, 0.85, 0.88, 0.90,
    0.92, 0.94, 0.96, 0.98, 1.00,
    1.02, 1.04, 1.06, 1.08, 1.10,
    1.12, 1.15, 1.22, 1.35, 1.48,
)
WALL_FACTORS: tuple[float, ...] = (
    0.78, 0.84, 0.86, 0.89, 0.91,
    0.93, 0.95, 0.97, 0.99, 1.01,
    1.03, 1.05, 1.07, 1.09, 1.11,
    1.14, 1.18, 1.25, 1.40, 1.55,
)
CALL_FACTORS: tuple[float, ...] = (
    0.50, 0.50, 0.75, 0.75, 1.00,
    1.00, 1.00, 1.00, 1.00, 1.00,
    1.00, 1.00, 1.00, 1.25, 1.25,
    1.50, 1.50, 1.75, 2.00, 2.00,
)


def plan_at(i: int) -> CouncilPlan:
    seats = tuple(f"s{j}" for j in range(2 + (i % 6)))
    rounds = 2 + (i % 5)
    return CouncilPlan(
        council_id=f"RC-{i:02d}",
        seats=seats,
        rounds=rounds,
        tokens_per_seat_turn=800 + 50 * i,
        tool_calls_per_seat_turn=0.5 + 0.1 * (i % 5),
        think_seconds_per_seat_turn=5.0 + 0.25 * i,
    )


def recorded_councils() -> list[dict]:
    if len(TOKEN_FACTORS) != 20 or len(WALL_FACTORS) != 20 or len(CALL_FACTORS) != 20:
        raise RuntimeError("corpus factors must be length 20")
    rows: list[dict] = []
    for i in range(20):
        plan = plan_at(i)
        est = estimate_cost(plan)
        actual = Cost(
            tokens=max(1, int(round(est.tokens * TOKEN_FACTORS[i]))),
            wall_clock_seconds=round(est.wall_clock_seconds * WALL_FACTORS[i], 4),
            external_calls=max(0, int(round(est.external_calls * CALL_FACTORS[i]))),
        )
        rows.append({"id": plan.council_id, "plan": plan, "actual": actual})
    return rows


def over_ceiling_fixture() -> tuple[CouncilPlan, OwnerCeiling, Cost]:
    plan = CouncilPlan(
        council_id="OVER-CEILING",
        seats=tuple(f"s{i}" for i in range(8)),
        rounds=8,
        tokens_per_seat_turn=2500,
        tool_calls_per_seat_turn=2.0,
        think_seconds_per_seat_turn=12.0,
    )
    est = estimate_cost(plan)
    ceiling = OwnerCeiling(
        tokens=max(1, est.tokens // 10),
        wall_clock_seconds=max(1.0, est.wall_clock_seconds / 10.0),
        external_calls=max(1, est.external_calls // 10),
    )
    return plan, ceiling, est


def under_ceiling_for(plan: CouncilPlan) -> OwnerCeiling:
    est = estimate_cost(plan)
    return OwnerCeiling(
        tokens=est.tokens * 10,
        wall_clock_seconds=est.wall_clock_seconds * 10.0 + 1.0,
        external_calls=est.external_calls * 10 + 10,
    )


def launch_spec(*, over_ceiling: bool, approval: dict | None = None) -> dict:
    spec: dict = {
        "id": "imp0352-launch",
        "participants": [
            {"id": "a", "vote": "yes"},
            {"id": "b", "vote": "yes"},
            {"id": "c", "vote": "yes"},
        ],
        "voting": {"rule": "majority", "quorum": 2},
        "seats": ["a", "b", "c"],
        "rounds": 4,
        "tokens_per_seat_turn": 2000,
        "tool_calls_per_seat_turn": 2.0,
        "think_seconds_per_seat_turn": 10.0,
        "artifacts": {"write": True},
    }
    plan = CouncilPlan.from_mapping(spec)
    est = estimate_cost(plan)
    if over_ceiling:
        spec["owner_ceiling"] = {
            "tokens": max(1, est.tokens // 20),
            "wall_clock_seconds": max(0.1, est.wall_clock_seconds / 20.0),
            "external_calls": 1,
        }
    else:
        spec["owner_ceiling"] = {
            "tokens": est.tokens * 10,
            "wall_clock_seconds": est.wall_clock_seconds * 10.0,
            "external_calls": est.external_calls * 10 + 10,
        }
    if approval is not None:
        spec["owner_approval"] = approval
    return spec
