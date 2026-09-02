#!/usr/bin/env python3
"""Probe 2: negative control — remove the resolution rule, fixture goes nondeterministic.

Spec 11343 nested-disagreement class: last-writer-wins (or any incidental order)
must not be how parent/child completion is decided. Both-states:

  * rule ON  → every shuffle of (child, parent) vs (parent, child) agrees
  * rule OFF → the same disagreement fixture yields more than one winner
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from tools.council.topology import nested as N  # noqa: E402

FIXTURE = HERE / "fixtures" / "disagreement.json"
ORDERS = (("child", "parent"), ("parent", "child"))


def _q(doc: dict, key: str) -> N.BoundedQuestion:
    raw = doc["questions"][key]
    return N.BoundedQuestion(
        question_id=raw["question_id"],
        prompt=raw["prompt"],
        max_rounds=int(raw["max_rounds"]),
    )


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0288-probe2 {msg}")
    return 1


def _winners(
    parent: dict,
    child: dict,
    question: N.BoundedQuestion,
    *,
    apply_rule: bool,
) -> list[bool]:
    out: list[bool] = []
    for order in ORDERS:
        res = N.run_nested(
            parent=parent,
            question=question,
            child_artifact=child,
            apply_resolution_rule=apply_rule,
            order=order,
        )
        out.append(bool(res.resolution.winner_complete))
        if apply_rule and res.resolution.rule_id != N.RESOLUTION_RULE_ID:
            raise AssertionError(f"rule on but rule_id={res.resolution.rule_id}")
        if apply_rule and res.resolution.incidental:
            raise AssertionError("rule on but incidental=True")
        if not apply_rule and not res.resolution.incidental:
            raise AssertionError("rule off but incidental=False")
        if not apply_rule and res.resolution.rule_id is not None:
            raise AssertionError("rule off but rule_id set")
    return out


def main() -> int:
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    leaf_q = _q(doc, "leaf")
    a = doc["parent_complete_child_incomplete"]

    with_rule = _winners(a["parent"], a["child"], leaf_q, apply_rule=True)
    without = _winners(a["parent"], a["child"], leaf_q, apply_rule=False)

    if len(set(with_rule)) != 1:
        return _fail(f"rule-on must be deterministic, got {with_rule}")
    if with_rule[0] is not False:
        return _fail(
            f"rule-on conservative conjunction must be INCOMPLETE, got {with_rule}"
        )
    if len(set(without)) <= 1:
        return _fail(
            "rule-off expected nondeterministic last-writer-wins "
            f"across orders, got {without}"
        )

    # Opposite disagreement also flips without the rule.
    b = doc["parent_incomplete_child_complete"]
    with_b = _winners(b["parent"], b["child"], leaf_q, apply_rule=True)
    without_b = _winners(b["parent"], b["child"], leaf_q, apply_rule=False)
    if len(set(with_b)) != 1 or with_b[0] is not False:
        return _fail(f"case-b rule-on expected [False, False], got {with_b}")
    if len(set(without_b)) <= 1:
        return _fail(f"case-b rule-off expected a flip, got {without_b}")

    # Averaging control: midpoint / majority-of-reports is not a winner.
    # With one COMPLETE and one INCOMPLETE, conjunction is INCOMPLETE, never True.
    if any(with_rule) or any(with_b):
        return _fail("averaging control failed: disagreement became COMPLETE")

    summary = {
        "probe": "probe2-resolution-rule-control",
        "unit_id": "IMP-0288",
        "pass": True,
        "negative_control": "remove-resolution-rule",
        "spec_class": "11343-nested-disagreement",
        "case_a_rule_on": with_rule,
        "case_a_rule_off": without,
        "case_b_rule_on": with_b,
        "case_b_rule_off": without_b,
        "deterministic_with_rule": True,
        "nondeterministic_without_rule": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(f"rule_on={with_rule} rule_off={without} case_b_off={without_b}")
    print("SUCCESS:IMP-0288-probe2 remove-rule negative control (nondeterministic)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
