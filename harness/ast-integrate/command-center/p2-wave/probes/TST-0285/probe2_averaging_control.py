#!/usr/bin/env python3
"""Probe 2: independent reviewer — averaging/majority control + both-states.

Does not trust coc.py's docstring. Reconstructs sibling verdicts by calling
the shared reducer, then asserts:

  * 1 COMPLETE + 1 INCOMPLETE does not become a midpoint or COMPLETE
  * 2-of-3 majority would be COMPLETE; conjunction stays INCOMPLETE
  * rule OFF last-writer-wins flips across sibling order
  * agreeing pair stays COMPLETE (silent good state)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from tools.council.shared_completion import judge as shared_judge  # noqa: E402
from tools.council.topology import coc  # noqa: E402
from tools.council.topology import nested as N  # noqa: E402

FIXTURE = HERE / "fixtures" / "sibling_disagreement.json"
ORDERS_2 = (
    ("council.alpha-done", "council.beta-blocked"),
    ("council.beta-blocked", "council.alpha-done"),
)


def _q(doc: dict, key: str) -> N.BoundedQuestion:
    raw = doc["questions"][key]
    return N.BoundedQuestion(
        question_id=raw["question_id"],
        prompt=raw["prompt"],
        max_rounds=int(raw["max_rounds"]),
    )


def _fail(msg: str) -> int:
    print(f"FAILED:TST-0285-probe2 {msg}")
    return 1


def _planted_average(completes: list[bool]) -> bool:
    n = len(completes)
    return (sum(1 for c in completes if c) / n) >= 0.5 if n else False


def _planted_majority(completes: list[bool]) -> bool:
    n = len(completes)
    return sum(1 for c in completes if c) > (n / 2)


def main() -> int:
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    q_alpha, q_beta, q_gamma = _q(doc, "alpha"), _q(doc, "beta"), _q(doc, "gamma")
    parent = doc["parent"]
    split = doc["split_done_not_done"]

    with_rule: list[bool] = []
    without: list[bool] = []
    for order in ORDERS_2:
        on = coc.fan_in(
            parent=parent,
            siblings=[split["done"], split["blocked"]],
            questions=[q_alpha, q_beta],
            apply_resolution_rule=True,
            order=order,
        )
        off = coc.fan_in(
            parent=parent,
            siblings=[split["done"], split["blocked"]],
            questions=[q_alpha, q_beta],
            apply_resolution_rule=False,
            order=order,
        )
        with_rule.append(bool(on.resolution.winner_complete))
        without.append(bool(off.resolution.winner_complete))
        if on.resolution.rule_id != coc.FANIN_RULE_ID:
            return _fail(f"rule on but rule_id={on.resolution.rule_id}")
        if on.resolution.incidental:
            return _fail("rule on but incidental=True")
        if off.resolution.incidental is not True:
            return _fail("rule off but incidental is not True")
        if off.resolution.rule_id is not None:
            return _fail("rule off but rule_id set")
        if not isinstance(on.parent.get("completion"), bool):
            return _fail(f"midpoint completion type={type(on.parent.get('completion'))}")
        recounted = []
        for row in on.parent.get("subcouncil_inputs_verbatim") or []:
            live = shared_judge(row["artifact"], locus="probe2-independent-rejudge")
            recounted.append(bool(live.complete))
            if bool(live.complete) != bool(row["complete"]):
                return _fail(f"independent rejudge mismatch {row['council_id']}")
        if recounted != [True, False]:
            return _fail(f"independent recount expected [True, False] got {recounted}")

    if len(set(with_rule)) != 1 or with_rule[0] is not False:
        return _fail(f"rule-on split must be [False, False], got {with_rule}")
    if len(set(without)) <= 1:
        return _fail(
            "rule-off expected last-writer-wins flip across orders, "
            f"got {without}"
        )

    planted_avg_split = _planted_average([True, False])
    if planted_avg_split is not True:
        return _fail("planted average of 1/2 should be COMPLETE (control is wired)")
    if with_rule[0] == planted_avg_split:
        return _fail("live winner matched planted average — averaging not rejected")

    maj = doc["majority_2_of_3"]
    res3 = coc.fan_in(
        parent=parent,
        siblings=[maj["alpha"], maj["beta"], maj["gamma"]],
        questions=[q_alpha, q_beta, q_gamma],
        apply_resolution_rule=True,
    )
    completes3 = [s.complete for s in res3.siblings]
    if completes3 != [True, True, False]:
        return _fail(f"2-of-3 sibling completes={completes3}")
    if res3.resolution.winner_complete:
        return _fail("2-of-3 majority must not complete the parent")
    if res3.resolution.majority_complete is not True:
        return _fail("rejected majority flag should be True on 2-of-3")
    if abs((res3.resolution.average or 0) - (2 / 3)) > 1e-9:
        return _fail(f"rejected average should be 2/3 got {res3.resolution.average}")
    if res3.parent.get("completion") is True or res3.parent.get("completion") == (2 / 3):
        return _fail("parent emitted majority or midpoint as completion")
    if _planted_majority(completes3) is not True:
        return _fail("planted majority of 2/3 should be True")
    if bool(res3.resolution.winner_complete) == _planted_majority(completes3):
        return _fail("live winner matched planted majority")

    ag = doc["agreeing_complete"]
    ok = coc.fan_in(
        parent=parent,
        siblings=[ag["alpha"], ag["beta"]],
        questions=[q_alpha, q_beta],
        apply_resolution_rule=True,
    )
    if not ok.resolution.winner_complete:
        return _fail("agreeing COMPLETE pair must stay COMPLETE")
    if ok.resolution.blocking_parties:
        return _fail("agreeing pair must not name blocking_parties")

    summary = {
        "probe": "probe2-averaging-control",
        "unit_id": "TST-0285",
        "pass": True,
        "negative_control": "remove-fanin-rule-last-writer-wins",
        "spec_class": "11343-nested-disagreement",
        "split_rule_on": with_rule,
        "split_rule_off": without,
        "planted_average_split": planted_avg_split,
        "majority_2_of_3": {
            "sibling_completes": completes3,
            "winner_complete": res3.resolution.winner_complete,
            "rejected_majority": res3.resolution.majority_complete,
            "rejected_average": res3.resolution.average,
        },
        "agreeing_complete": ok.resolution.winner_complete,
        "independent_rejudge": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"rule_on={with_rule} rule_off={without} "
        f"2of3_winner={res3.resolution.winner_complete} "
        f"majority_rejected={res3.resolution.majority_complete}"
    )
    print("SUCCESS:TST-0285-probe2 averaging-control independent-rejudge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
