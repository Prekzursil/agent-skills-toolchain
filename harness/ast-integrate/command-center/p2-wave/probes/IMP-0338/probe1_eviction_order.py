#!/usr/bin/env python3
"""Named probe 1: eviction order matches the documented policy; per-seat tokens fit.

Evidence signal 1: measured token counts on two seats against their declared
budgets. What is dropped first is filler, then oldest history. Required
anchors remain in the assembled prompt.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.context import (  # noqa: E402
    EVICTION_ORDER,
    assemble_council,
    count_tokens,
    eviction_policy,
    measure_token_counts,
    ranks_are_non_decreasing,
    retention_check,
    seat_from_mapping,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0338-probe1 {msg}")
    return 1


def words(n: int, tag: str) -> str:
    return " ".join(f"{tag}{i:02d}" for i in range(n))


def seat_analyst() -> dict:
    return {
        "seat_id": "analyst",
        "role": {
            "id": "analyst",
            "identity": "You are the cost analyst for this council.",
            "elaboration": words(10, "aelab"),
        },
        "partition": {
            "id": "P-A",
            "body": "Only the analyst sees " + words(6, "pa") + " CANARY_A",
        },
        "task": "Weigh required anchors ANCHOR_COST and ANCHOR_RISK.",
        "filler": words(18, "afill"),
        "history": [
            {"turn_index": i, "text": words(8, f"ah{i}")} for i in range(4)
        ],
        "evidence": [
            {
                "id": "ANCHOR_COST",
                "required": True,
                "body": "Measured cost is forty two units.",
            },
            {
                "id": "ANCHOR_RISK",
                "required": True,
                "body": "Risk row seven remains in scope.",
            },
            {"id": "OPT_NOTE", "required": False, "body": words(14, "aopt")},
        ],
    }


def seat_critic() -> dict:
    return {
        "seat_id": "critic",
        "role": {
            "id": "critic",
            "identity": "You are the independent critic.",
            "elaboration": words(8, "celab"),
        },
        "partition": {
            "id": "P-B",
            "body": "Only the critic sees " + words(6, "pb") + " CANARY_B",
        },
        "task": "Challenge the cost case using ANCHOR_COST.",
        "filler": words(16, "cfill"),
        "history": [
            {"turn_index": i, "text": words(7, f"ch{i}")} for i in range(3)
        ],
        "evidence": [
            {
                "id": "ANCHOR_COST",
                "required": True,
                "body": "Measured cost is forty two units.",
            },
            {
                "id": "ANCHOR_CRITIQUE",
                "required": True,
                "body": "Critique ledger row three is required.",
            },
            {"id": "OPT_ASIDE", "required": False, "body": words(12, "copt")},
        ],
    }


def main() -> int:
    policy = eviction_policy()
    if policy["drop_first_to_last"] != list(EVICTION_ORDER):
        return fail("policy data drifted from EVICTION_ORDER")
    if policy["answers"]["what_is_dropped_first"] != "filler":
        return fail("documented first drop is not filler")
    if policy["answers"]["can_required_anchors_be_evicted"] is not False:
        return fail("policy claims required anchors can be evicted")

    raw_seats = [seat_analyst(), seat_critic()]
    seats = [seat_from_mapping(s) for s in raw_seats]
    unconstrained = assemble_council(seats, default_budget=10**6)
    if any(a.dropped for a in unconstrained):
        return fail("unconstrained assembly dropped segments")

    # Subtract enough that filler is gone and at least one history turn drops,
    # while remaining above pinned size (required anchors stay).
    budgets = {a.seat_id: a.tokens - 40 for a in unconstrained}
    tight = assemble_council(
        [
            {**raw_seats[0], "budget_tokens": budgets["analyst"]},
            {**raw_seats[1], "budget_tokens": budgets["critic"]},
        ]
    )
    if len(tight) != 2:
        return fail(f"expected 2 seats, got {len(tight)}")

    for asm in tight:
        if not asm.dropped:
            return fail(f"{asm.seat_id} dropped nothing under a tighter budget")
        if asm.dropped[0].kind != "filler":
            return fail(
                f"{asm.seat_id} first drop was {asm.dropped[0].kind}, not filler"
            )
        kinds = [d.kind for d in asm.dropped]
        if "history" not in kinds:
            return fail(f"{asm.seat_id} never reached history eviction: {kinds}")
        history_seq = [d.sequence for d in asm.dropped if d.kind == "history"]
        if history_seq != sorted(history_seq):
            return fail(f"{asm.seat_id} history was not dropped oldest-first: {history_seq}")
        if not ranks_are_non_decreasing(asm.dropped):
            return fail(f"{asm.seat_id} drop ranks are not non-decreasing")
        if asm.tokens != count_tokens(asm.prompt):
            return fail(f"{asm.seat_id} measured tokens diverged from contract tokenizer")
        if asm.tokens > asm.budget_tokens:
            return fail(
                f"{asm.seat_id} tokens={asm.tokens} over budget={asm.budget_tokens}"
            )
        check = retention_check(
            asm.prompt,
            ["ANCHOR_COST", "ANCHOR_RISK"]
            if asm.seat_id == "analyst"
            else ["ANCHOR_COST", "ANCHOR_CRITIQUE"],
        )
        if check.fired:
            return fail(f"{asm.seat_id} retention fired after legal eviction: {check.missing}")

    analyst = next(a for a in tight if a.seat_id == "analyst")
    critic = next(a for a in tight if a.seat_id == "critic")
    if "CANARY_A" not in analyst.prompt or "CANARY_B" in analyst.prompt:
        return fail("analyst partition did not hold")
    if "CANARY_B" not in critic.prompt or "CANARY_A" in critic.prompt:
        return fail("critic partition did not hold")
    if "id=ANCHOR_COST" not in analyst.prompt or "id=ANCHOR_RISK" not in analyst.prompt:
        return fail("analyst lost a required anchor")
    if "id=ANCHOR_COST" not in critic.prompt or "id=ANCHOR_CRITIQUE" not in critic.prompt:
        return fail("critic lost a required anchor")

    rows = measure_token_counts(tight)
    payload = {
        "probe": "probe1-eviction-order",
        "unit_id": "IMP-0338",
        "drop_first": "filler",
        "policy": policy["drop_first_to_last"],
        "seats": rows,
        "analyst_first_drop": analyst.dropped[0].kind,
        "critic_first_drop": critic.dropped[0].kind,
        "analyst_dropped_kinds": [d.kind for d in analyst.dropped],
        "critic_dropped_kinds": [d.kind for d in critic.dropped],
        "analyst_history_drop_seq": [
            d.sequence for d in analyst.dropped if d.kind == "history"
        ],
        "anchors_survived": True,
        "partitions_held": True,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "first_drop=filler "
        f"analyst_tokens={analyst.tokens}/{analyst.budget_tokens} "
        f"critic_tokens={critic.tokens}/{critic.budget_tokens}"
    )
    print("SUCCESS:IMP-0338-probe1 eviction order and per-seat token counts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
