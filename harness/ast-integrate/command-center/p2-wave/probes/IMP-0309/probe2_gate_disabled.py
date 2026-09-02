#!/usr/bin/env python3
"""Probe 2: FC-11338 negative control — disable the gate, fixture stops early.

Both-states: the same instant-consensus fixture STOPs with the gate off
and does NOT stop with the gate on. A probe silent in both states
measures nothing.

Reviewer path starts from these tests, not the author's summary: AST-inspect
minimum.py and require evaluate() to branch on each floor.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.stopping.minimum import (  # noqa: E402
    CEILING_ESCALATE,
    CONDITION_BRIEFS,
    FLOOR_BLOCK,
    GATE_DISABLED_STOP,
    evaluate,
    format_condition_table,
    run_rounds,
)

FIXTURE = HERE / "fixtures" / "instant_consensus.json"
SRC = REPO / "tools" / "council" / "stopping" / "minimum.py"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0309-probe2 {msg}")
    return 1


def review_source(path: Path) -> dict:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn_names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    evaluate_returns_constant_true = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != "evaluate":
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.Return) and isinstance(sub.value, ast.Constant):
                if sub.value.value is True:
                    evaluate_returns_constant_true = True
    return {
        "evaluate_present": "evaluate" in fn_names,
        "evaluate_returns_constant_true": evaluate_returns_constant_true,
        "reasons": {
            "FLOOR_BLOCK": "FLOOR_BLOCK" in src,
            "GATE_DISABLED_STOP": "GATE_DISABLED_STOP" in src,
            "CEILING_ESCALATE": "CEILING_ESCALATE" in src,
        },
        "floor_ids": {
            "rounds": "CONDITION_ROUNDS" in src,
            "independent_briefs": "CONDITION_BRIEFS" in src,
            "objections_considered": "CONDITION_OBJECTIONS" in src,
        },
        "gate_enabled_flag": "gate_enabled" in src,
        "bytes": len(src.encode("utf-8")),
    }


def main() -> int:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    spec_on = dict(raw["spec"])
    spec_on["gate_enabled"] = True
    spec_off = dict(raw["spec"])
    spec_off["gate_enabled"] = False
    states = list(raw["rounds"])

    on = run_rounds(spec_on, states)
    off = run_rounds(spec_off, states)
    on_d = on.decisions[0]
    off_d = off.decisions[0]

    print("GATE ON")
    print(format_condition_table(on_d))
    print("GATE OFF")
    print(format_condition_table(off_d))

    if not off.stopped or not off_d.may_stop:
        return fail("gate-disabled fixture did not stop (negative control inert)")
    if off_d.reason != GATE_DISABLED_STOP:
        return fail(f"gate-off reason {off_d.reason} != GATE_DISABLED_STOP")
    if CONDITION_BRIEFS not in off_d.unmet:
        return fail("gate-off table must still show unmet independent_briefs")
    if on.stopped or on_d.may_stop:
        return fail("gate-on instant consensus stopped (both-states collapsed)")
    if on_d.reason != FLOOR_BLOCK:
        return fail(f"gate-on reason {on_d.reason} != FLOOR_BLOCK")
    if on.stopped == off.stopped:
        return fail("enabled and disabled traces did not discriminate")

    ceiling = evaluate(
        spec_on,
        {
            "rounds_completed": int(spec_on["max_rounds"]),
            "independent_brief_authors": [],
            "objection_ids_considered": [],
            "stop_expression_true": True,
            "consensus": True,
        },
    )
    print(
        f"ceiling may_stop={ceiling.may_stop} reason={ceiling.reason} "
        f"ceiling_reached={ceiling.ceiling_reached} unmet={list(ceiling.unmet)}"
    )
    if ceiling.may_stop or ceiling.reason != CEILING_ESCALATE:
        return fail(f"ceiling with unmet floors must escalate, got {ceiling.reason}")

    review = review_source(SRC)
    print(json.dumps({"reviewer": review}, sort_keys=True))
    if not review["evaluate_present"]:
        return fail("reviewer: evaluate() missing")
    if review["evaluate_returns_constant_true"]:
        return fail("reviewer: evaluate returns constant True")
    if not all(review["reasons"].values()):
        return fail(f"reviewer: missing reason constants {review['reasons']}")
    if not all(review["floor_ids"].values()):
        return fail(f"reviewer: missing floor ids {review['floor_ids']}")
    if not review["gate_enabled_flag"]:
        return fail("reviewer: gate_enabled flag absent")

    payload = {
        "probe": "probe2-gate-disabled-negative-control",
        "unit_id": "IMP-0309",
        "failure_class": "FC-11338",
        "gate_on_stopped": on.stopped,
        "gate_off_stopped": off.stopped,
        "gate_on_reason": on_d.reason,
        "gate_off_reason": off_d.reason,
        "both_states_discriminate": on.stopped != off.stopped,
        "ceiling_reason": ceiling.reason,
        "reviewer_pass": True,
        "pass": True,
        "verbatim_negative_control": (
            "State meant to reject: instant-consensus round 1 with zero "
            "independent briefs and a true stopping expression. Check with "
            "gate_enabled=false: may_stop=true reason=GATE_DISABLED_STOP "
            "(FC-11338). Check with gate_enabled=true: may_stop=false "
            "reason=FLOOR_BLOCK unmet includes independent_briefs."
        ),
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:IMP-0309-probe2 gate-disabled fixture stops early; both-states discriminate"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
