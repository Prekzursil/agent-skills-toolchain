#!/usr/bin/env python3
"""Named probe 2: risk class immutable after start; late reclass mutant fails the test."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.risk import (  # noqa: E402
    EVENT_MUTATION_REFUSED,
    EVENT_START_WITHOUT_CLASS,
    DeliberationSession,
    at_floor,
    evaluate_config,
    high_under_low_attack,
    immutability_holds,
    late_declaration_attack,
)

ART = REPO / "command-center/receipts/IMP-0358.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:IMP-0358-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "IMP-0358":
        print("FAILED:IMP-0358-probe2 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:IMP-0358" not in text:
        print("FAILED:IMP-0358-probe2 sentinel absent")
        return 1

    live = high_under_low_attack(allow_late_reclassification=False)
    mut = live["mutation"]
    if mut.get("accepted") is not False:
        print("FAILED:IMP-0358-probe2 production mutation was accepted")
        return 1
    event = mut.get("event") or {}
    if event.get("type") != EVENT_MUTATION_REFUSED:
        print("FAILED:IMP-0358-probe2 missing mutation-refused event", event)
        return 1
    if live["bound_class"] != "LOW":
        print("FAILED:IMP-0358-probe2 class mutated despite refusal", live["bound_class"])
        return 1
    if live["high_risk_taken_under_low_config"] is not False:
        print("FAILED:IMP-0358-probe2 high-under-low succeeded on production path")
        return 1
    if live["immutability_holds"] is not True:
        print("FAILED:IMP-0358-probe2 production immutability_holds is False")
        return 1
    if live["conclude"].get("accepted") is not True:
        print("FAILED:IMP-0358-probe2 production conclude failed", live["conclude"])
        return 1

    late = late_declaration_attack()
    if not late["refused_start_without_class"]:
        print("FAILED:IMP-0358-probe2 start-without-class was not refused", late)
        return 1
    if (late["start"].get("event") or {}).get("type") != EVENT_START_WITHOUT_CLASS:
        print("FAILED:IMP-0358-probe2 start-without-class event missing")
        return 1
    if late["started"]:
        print("FAILED:IMP-0358-probe2 start-without-class actually started", late)
        return 1
    if (late["start"].get("accepted") is True) and late["bound_class"] == "HIGH":
        print("FAILED:IMP-0358-probe2 late HIGH declaration bound a run", late)
        return 1

    # Same-class restatement after start is a no-op, not a mutation.
    same = DeliberationSession(config=at_floor("HIGH"), risk_class="HIGH")
    if same.start().get("accepted") is not True:
        print("FAILED:IMP-0358-probe2 HIGH at-floor start refused")
        return 1
    noop = same.reclassify("HIGH")
    if not noop.get("noop"):
        print("FAILED:IMP-0358-probe2 same-class restatement was not a no-op", noop)
        return 1

    # Negative control: allow late reclassification and the immutability test FAILS.
    mutant = DeliberationSession(
        config=at_floor("LOW"),
        risk_class="LOW",
        allow_late_reclassification=True,
    )
    if mutant.start().get("accepted") is not True:
        print("FAILED:IMP-0358-probe2 mutant failed to start")
        return 1
    if immutability_holds(mutant, new_class="HIGH"):
        print(
            "FAILED:IMP-0358-probe2 negative control inert: "
            "immutability still holds when late reclassification is allowed"
        )
        return 1
    if mutant.bound_class != "HIGH":
        print("FAILED:IMP-0358-probe2 mutant did not take HIGH", mutant.bound_class)
        return 1
    high_eval = evaluate_config("HIGH", mutant.config)
    if high_eval["accepted"] is not False:
        print("FAILED:IMP-0358-probe2 mutant HIGH still meets HIGH floors")
        return 1
    attack = high_under_low_attack(allow_late_reclassification=True)
    if attack["high_risk_taken_under_low_config"] is not True:
        print("FAILED:IMP-0358-probe2 mutant did not take HIGH under LOW config", attack)
        return 1
    if attack["immutability_holds"] is not False:
        print("FAILED:IMP-0358-probe2 mutant immutability_holds did not FAIL")
        return 1

    payload = {
        "adjudicated": True,
        "pass": True,
        "probe": "probe2-immutability",
        "unit_id": "IMP-0358",
        "production_mutation_refused": True,
        "production_event_type": event.get("type"),
        "production_from": event.get("from_class"),
        "production_to": event.get("to_class"),
        "late_declaration_refused": True,
        "negative_control_immutability_failed": True,
        "mutant_high_under_low": True,
        "high_floors_unmet_on_mutant_config": high_eval["violations"],
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:IMP-0358-probe2 immutability and late-reclass negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
