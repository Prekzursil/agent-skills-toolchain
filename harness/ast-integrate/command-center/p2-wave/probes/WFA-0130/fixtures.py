"""Matched-case arms for WFA-0130 both-states controls.

n=40. Sources A and B share the same oracle vector so copying A cannot
manufacture complementarity vs B. They differ only in stage_count.
"""
from __future__ import annotations

from typing import Any

N = 40


def _case(
    i: int,
    *,
    oracle: bool,
    attempted: bool,
    fail_event: bool,
    recovered: bool,
    usable: bool,
    stages: int,
) -> dict[str, Any]:
    return {
        "case_id": f"c{i:02d}",
        "oracle_pass": bool(oracle),
        "attempted": bool(attempted),
        "failure_event": bool(fail_event),
        "recovered": bool(recovered),
        "schema_valid_complete": bool(usable),
        "human_interventions": 0 if usable else 1,
        "stage_count": int(stages),
    }


def make_arm(
    arm_id: str,
    *,
    stages: int,
    oracle_upto: int,
    attempted_upto: int,
    recover_upto: int,
    usable_upto: int,
    extra_oracle: tuple[int, ...] = (),
) -> dict[str, Any]:
    extra = set(extra_oracle)
    cases = []
    for i in range(N):
        oracle = i < oracle_upto or i in extra
        attempted = i < attempted_upto or oracle
        fail_event = not oracle
        recovered = fail_event and i < recover_upto
        usable = i < usable_upto
        cases.append(
            _case(
                i,
                oracle=oracle,
                attempted=attempted,
                fail_event=fail_event,
                recovered=recovered,
                usable=usable,
                stages=stages,
            )
        )
    return {
        "arm_id": arm_id,
        "stage_count": stages,
        "n": N,
        "cases": cases,
    }


def source_a() -> dict[str, Any]:
    # C=24/40=0.60  V=32/40=0.80  R=8/16=0.50  U=20/40=0.50
    return make_arm(
        "source-A",
        stages=3,
        oracle_upto=24,
        attempted_upto=32,
        recover_upto=32,
        usable_upto=20,
    )


def source_b() -> dict[str, Any]:
    # Same four metrics as A; only stage_count differs.
    return make_arm(
        "source-B",
        stages=4,
        oracle_upto=24,
        attempted_upto=32,
        recover_upto=32,
        usable_upto=20,
    )


def stage_padded() -> dict[str, Any]:
    """Identical case outcomes to the sources, more stages. Must REJECT."""
    return make_arm(
        "fusion-stage-padded",
        stages=30,
        oracle_upto=24,
        attempted_upto=32,
        recover_upto=32,
        usable_upto=20,
    )


def genuine_improvement() -> dict[str, Any]:
    """Material lift on all four metrics. Must ACCEPT (OUTPERFORM)."""
    # C=28/40=0.70  V=36/40=0.90  R=10/12≈0.833  U=28/40=0.70
    return make_arm(
        "fusion-genuine-improvement",
        stages=99,
        oracle_upto=28,
        attempted_upto=36,
        recover_upto=38,
        usable_upto=28,
    )


def complement_only() -> dict[str, Any]:
    """Recovers one source-fail case; mean deltas stay below MES. Must ACCEPT."""
    # extra oracle on c24: C=25/40=0.625 (Δ=+0.025 < 0.05)
    # complement_recall = 1/16 = 0.0625 >= 0.05
    # remaining fails 25..39 (15); recover 25..32 (8) so R=8/15≈0.533
    return make_arm(
        "fusion-complement-only",
        stages=5,
        oracle_upto=24,
        attempted_upto=32,
        recover_upto=33,
        usable_upto=20,
        extra_oracle=(24,),
    )


def worse() -> dict[str, Any]:
    """Regresses every metric. Must REJECT."""
    return make_arm(
        "fusion-worse",
        stages=2,
        oracle_upto=16,
        attempted_upto=24,
        recover_upto=20,
        usable_upto=12,
    )


def all_sources() -> list[dict[str, Any]]:
    return [source_a(), source_b()]
