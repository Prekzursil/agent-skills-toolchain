#!/usr/bin/env python3
"""Probe 1: instant-consensus fixture must not stop; each floor independently blocks.

Catalog evidence: (1) instant-consensus fixture does not stop early;
(2) the gate's condition table is printed with measured values at the
candidate-stop instant.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.stopping.minimum import (  # noqa: E402
    CONDITION_BRIEFS,
    CONDITION_OBJECTIONS,
    CONDITION_ROUNDS,
    FLOOR_BLOCK,
    STOP_ALLOWED,
    FloorSpec,
    FloorValidationError,
    evaluate,
    format_condition_table,
    run_rounds,
)

FIXTURE = HERE / "fixtures" / "instant_consensus.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0309-probe1 {msg}")
    return 1


def main() -> int:
    if not FIXTURE.is_file():
        return fail(f"missing fixture {FIXTURE}")
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    spec = dict(raw["spec"])
    spec["gate_enabled"] = True
    states = list(raw["rounds"])
    trace = run_rounds(spec, states)
    decision = trace.decisions[0]
    table_text = format_condition_table(decision)
    print(table_text)
    print(
        json.dumps(
            {
                "probe": "probe1-instant-consensus",
                "fixture_id": raw.get("id"),
                "stopped": trace.stopped,
                "may_stop": decision.may_stop,
                "reason": decision.reason,
                "unmet": list(decision.unmet),
                "condition_table": [row.as_dict() for row in decision.condition_table],
                "stop_expression_true": decision.stop_expression_true,
            },
            sort_keys=True,
        )
    )
    if trace.stopped or decision.may_stop:
        return fail("instant-consensus fixture stopped with gate enabled")
    if decision.reason != FLOOR_BLOCK:
        return fail(f"expected FLOOR_BLOCK got {decision.reason}")
    if CONDITION_BRIEFS not in decision.unmet:
        return fail("independent_briefs must be unmet on instant consensus")
    if decision.stop_expression_true is not True:
        return fail("stop expression was true; floors, not the expression, must block")

    independent_cases = [
        {
            "id": "only-rounds-unmet",
            "unmet": CONDITION_ROUNDS,
            "state": {
                "rounds_completed": 1,
                "independent_brief_authors": ["alice", "bob"],
                "objection_ids_considered": ["obj-1"],
                "stop_expression_true": True,
                "consensus": True,
            },
        },
        {
            "id": "only-briefs-unmet",
            "unmet": CONDITION_BRIEFS,
            "state": {
                "rounds_completed": int(spec["min_rounds"]),
                "independent_brief_authors": ["alice"],
                "objection_ids_considered": ["obj-1"],
                "stop_expression_true": True,
                "consensus": True,
            },
        },
        {
            "id": "only-objections-unmet",
            "unmet": CONDITION_OBJECTIONS,
            "state": {
                "rounds_completed": int(spec["min_rounds"]),
                "independent_brief_authors": ["alice", "bob"],
                "objection_ids_considered": [],
                "stop_expression_true": True,
                "consensus": True,
            },
        },
    ]
    independent = []
    for case in independent_cases:
        d = evaluate(spec, case["state"])
        independent.append(
            {
                "id": case["id"],
                "unmet": list(d.unmet),
                "reason": d.reason,
                "may_stop": d.may_stop,
            }
        )
        print(
            f"independent {case['id']} unmet={list(d.unmet)} "
            f"reason={d.reason} may_stop={d.may_stop}"
        )
        if d.may_stop or d.reason != FLOOR_BLOCK:
            return fail(f"{case['id']} did not independently block")
        if d.unmet != (case["unmet"],):
            return fail(f"{case['id']} expected unmet=({case['unmet']},) got {d.unmet}")

    all_met = evaluate(
        spec,
        {
            "rounds_completed": int(spec["min_rounds"]),
            "independent_brief_authors": ["alice", "bob"],
            "objection_ids_considered": ["obj-1"],
            "stop_expression_true": True,
            "consensus": True,
        },
    )
    print(
        f"all_floors_met may_stop={all_met.may_stop} reason={all_met.reason} "
        f"unmet={list(all_met.unmet)}"
    )
    if not all_met.may_stop or all_met.reason != STOP_ALLOWED or all_met.unmet:
        return fail("all-floors-met must allow stop (over-blocking control)")

    clones = evaluate(
        spec,
        {
            "rounds_completed": int(spec["min_rounds"]),
            "independent_brief_authors": ["alice", "alice"],
            "objection_ids_considered": ["obj-1"],
            "stop_expression_true": True,
        },
    )
    print(
        f"duplicate_authors unmet={list(clones.unmet)} "
        f"measured_briefs={clones.condition_table[1].measured}"
    )
    if clones.may_stop or CONDITION_BRIEFS not in clones.unmet:
        return fail("duplicate authors inflated independent brief count")

    for bad, path in (
        ({**spec, "min_rounds": 0}, "spec.min_rounds"),
        ({**spec, "min_independent_briefs": 0}, "spec.min_independent_briefs"),
        ({**spec, "max_rounds": 1}, "spec.max_rounds"),
    ):
        try:
            FloorSpec.from_obj(bad)
        except FloorValidationError as exc:
            print(f"validation_reject path={exc.path} reason={exc.reason}")
            if exc.path != path:
                return fail(f"validation path {exc.path} != {path}")
        else:
            return fail(f"expected validation reject for {path}")

    payload = {
        "pass": True,
        "probe": "probe1-instant-consensus",
        "unit_id": "IMP-0309",
        "stopped": False,
        "reason": decision.reason,
        "unmet": list(decision.unmet),
        "condition_table": [row.as_dict() for row in decision.condition_table],
        "condition_table_printed": True,
        "independent_floor_blocks": independent,
        "all_floors_met_allows_stop": True,
        "duplicate_authors_blocked": True,
        "validation_rejects_zero_floors": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:IMP-0309-probe1 instant-consensus blocked; each floor independently blocks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
