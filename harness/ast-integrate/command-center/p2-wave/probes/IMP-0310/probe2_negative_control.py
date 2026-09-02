#!/usr/bin/env python3
"""IMP-0310 probe 2: converging run must not escalate (negative control).

Also both-states: planting a wait-cycle freeze into that same run must fire,
and a never-returned seat is stalled_runtime rather than deadlock.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.stopping.deadlock import (  # noqa: E402
    CLASS_DEADLOCK,
    CLASS_STALLED,
    RUNG_NONE,
    RUNG_OWNER,
    RUNG_PROTOCOL,
    RUNG_REPLACE,
    STALL_ROUNDS,
    converging_run,
    escalate,
    evaluate,
    plant_deadlock,
    stalled_runtime_run,
)

OUT = HERE / "probe2-negative-control.raw.json"


def main() -> int:
    good = converging_run()
    good_v = evaluate(good)
    if good_v["deadlock"] or good_v["escalated"] or good_v["escalation"]["rung"] != RUNG_NONE:
        print("FAILED:IMP-0310-probe2 converging run was escalated", good_v["escalation"])
        return 1
    if good_v["classification"] == CLASS_DEADLOCK:
        print("FAILED:IMP-0310-probe2 converging classified as deadlock")
        return 1

    planted = plant_deadlock(good)
    bad_v = evaluate(planted)
    if not bad_v["deadlock"] or not bad_v["escalated"]:
        print("FAILED:IMP-0310-probe2 planted wait-cycle did not deadlock", bad_v["terminal"])
        return 1
    if bad_v["escalation"]["rung"] != RUNG_REPLACE:
        print("FAILED:IMP-0310-probe2 first rung was not replace", bad_v["escalation"])
        return 1
    named = bad_v["escalation"].get("named_seats") or []
    if "alice" not in named or "bob" not in named:
        print("FAILED:IMP-0310-probe2 replace did not name the cycled seats", named)
        return 1

    # Disable the stall window: the planted freeze is only STALL_ROUNDS long.
    disabled = evaluate(planted, stall_rounds=10**6)
    if disabled["deadlock"] or disabled["escalated"]:
        print("FAILED:IMP-0310-probe2 disabled gate still escalated")
        return 1

    second = escalate(bad_v["terminal"], prior=[bad_v["escalation"]])
    if second["rung"] != RUNG_PROTOCOL:
        print("FAILED:IMP-0310-probe2 second rung was not protocol_change", second)
        return 1
    third = escalate(bad_v["terminal"], prior=[bad_v["escalation"], second])
    if third["rung"] != RUNG_OWNER:
        print("FAILED:IMP-0310-probe2 third rung was not owner_intervention", third)
        return 1
    for field in ("question", "recommendation", "default_if_silent"):
        if not third.get(field):
            print(f"FAILED:IMP-0310-probe2 owner payload missing {field}")
            return 1
    q = third["question"]
    if q.count("?") > 1:
        print("FAILED:IMP-0310-probe2 owner asked more than one question")
        return 1

    stalled = evaluate(stalled_runtime_run())
    if stalled["classification"] != CLASS_STALLED:
        print("FAILED:IMP-0310-probe2 hung seat was not stalled_runtime", stalled["classification"])
        return 1
    if stalled["deadlock"] or stalled["escalated"]:
        print("FAILED:IMP-0310-probe2 stalled runtime used the deadlock ladder")
        return 1

    restored = evaluate(copy.deepcopy(good))
    if restored["escalated"] or restored["deadlock"]:
        print("FAILED:IMP-0310-probe2 unplanted converging run did not stay silent")
        return 1

    doc = {
        "probe": "probe2-negative-control",
        "unit_id": "IMP-0310",
        "pass": True,
        "silent_on_converging": True,
        "fired_on_planted_deadlock": True,
        "silent_when_gate_disabled": True,
        "stalled_runtime_not_deadlock": True,
        "escalation_ladder": [RUNG_REPLACE, RUNG_PROTOCOL, RUNG_OWNER],
        "owner_question": third["question"],
        "owner_recommendation": third["recommendation"],
        "owner_default_if_silent": third["default_if_silent"],
        "stall_rounds": STALL_ROUNDS,
        "converging_classification": good_v["classification"],
        "planted_classification": bad_v["classification"],
        "stalled_classification": stalled["classification"],
        "named_seats": named,
        "deadlocked_proposition": bad_v["escalation"].get("deadlocked_proposition"),
    }
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(
        "converging_escalated=False planted_deadlock=True gate_disabled_silent=True "
        f"stalled_runtime={stalled['classification']} ladder=replace,protocol_change,owner_intervention"
    )
    print("SUCCESS:IMP-0310-probe2 converging run not escalated (both-states)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
