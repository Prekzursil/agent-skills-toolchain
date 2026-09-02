#!/usr/bin/env python3
"""Probe 2: reason diversity, task-span grounding, legal false-positive rate.

Mechanically different from probe 1: this inspects reason *strings* and
task-span membership, and it reports the legal false-positive rate on
tasks with no legal dimension. Probe 1 only checks role set inclusion.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.participants.select_auto import (  # noqa: E402
    BOILERPLATE_MARKERS,
    compose,
    grounding_report,
    legal_false_positive_report,
    reason_diversity_report,
    roles_of,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0267-probe2 {msg}")
    return 1


def load_fixtures() -> dict:
    return json.loads((HERE / "fixtures.json").read_text(encoding="utf-8"))


def main() -> int:
    fx = load_fixtures()
    tasks = list(fx["archetypes"]) + [fx["missing_expertise"]]
    per_task = []
    for item in tasks:
        comp = compose(item["task"])
        seats = comp["seats"]
        div = reason_diversity_report(seats)
        ground = grounding_report(item["task"], seats)
        print(
            f"task {item['id']} unique_reasons={div['n_unique']}/{div['n_seats']} "
            f"grounded={ground['ok']} duplicates={div['duplicate_reasons'][:2]}"
        )
        if not div["ok"]:
            return fail(f"{item['id']} identical reasons {div['duplicate_reasons']}")
        if not ground["ok"]:
            return fail(f"{item['id']} ungrounded {ground['rows']}")
        per_task.append(
            {
                "id": item["id"],
                "n_seats": div["n_seats"],
                "n_unique": div["n_unique"],
                "grounded": True,
            }
        )

    fpr = legal_false_positive_report(fx["non_legal"])
    print(
        f"legal_false_positive n={fpr['n']} fires={fpr['fires']} "
        f"rate={fpr['rate']} fired={fpr['fired_ids']}"
    )
    if not fpr["ok"]:
        return fail(f"legal seated on non-legal tasks {fpr['fired_ids']}")
    if fpr["n"] < 4:
        return fail(f"need >=4 non-legal controls, got {fpr['n']}")

    # Both-states: identical boilerplate reasons must be rejected by the
    # diversity check, and unquoted boilerplate must fail grounding.
    live = compose(fx["archetypes"][0]["task"])
    mutant = copy.deepcopy(live["seats"])
    for seat in mutant:
        seat["reason"] = "standard council role seated for expertise"
        seat["task_spans"] = []
        seat["source"] = "auto"
        seat["grounding"] = "task-feature"
    div_bad = reason_diversity_report(mutant)
    ground_bad = grounding_report(fx["archetypes"][0]["task"], mutant)
    if div_bad["ok"]:
        return fail("diversity check accepted identical boilerplate reasons")
    if ground_bad["ok"]:
        return fail("grounding check accepted span-free boilerplate")
    if BOILERPLATE_MARKERS[0] not in mutant[0]["reason"]:
        return fail("mutant did not carry the boilerplate marker")
    print(
        f"mutant_rejected diversity_ok={div_bad['ok']} grounding_ok={ground_bad['ok']}"
    )

    # Confirm a live non-legal composition has no legal role (single-task check
    # independent of the rate aggregator).
    control = compose(fx["non_legal"][0]["task"])
    if "legal" in roles_of(control):
        return fail("mergesort control seated legal")

    summary = {
        "grounded_tasks": per_task,
        "legal_false_positive_rate": fpr["rate"],
        "legal_false_positive_n": fpr["n"],
        "legal_false_positive_fires": fpr["fires"],
        "mutant_diversity_rejected": not div_bad["ok"],
        "mutant_grounding_rejected": not ground_bad["ok"],
        "pass": True,
        "probe": "probe2-reasons-and-negatives",
        "unit_id": "IMP-0267",
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:IMP-0267-probe2 reason diversity, grounding, legal false-positive rate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
