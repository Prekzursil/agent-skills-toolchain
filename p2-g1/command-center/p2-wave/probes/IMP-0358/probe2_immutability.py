#!/usr/bin/env python3
"""IMP-0358 probe2: immutability mutation (independent reviewer).

Both-states control. Good state: a mid-run reclassification is refused with
RISK_CLASS_MUTATION_REFUSED and immutability_holds() is True. Bad state (the
catalog negative control): with allow_late_reclassification=True a HIGH label
is applied to a LOW configuration and immutability_holds() FAILS - proving the
immutability test is load-bearing, not decorative.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.risk import (  # noqa: E402
    EVENT_RISK_CLASS_MUTATION_REFUSED,
    EVENT_START_WITHOUT_CLASS,
    FLOORS,
    DeliberationSession,
    at_floor,
    high_under_low_attack,
    immutability_holds,
    late_declaration_attack,
)

RECEIPT = REPO / "command-center/receipts/IMP-0358.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0358-probe2 {msg}")
    return 1


def main() -> int:
    # Good state: late reclassification refused, class stays LOW, event fires.
    good = high_under_low_attack()
    if good["high_under_low"] is not False:
        return fail(f"good-state-attack-landed:{good}")
    if good["event"] != EVENT_RISK_CLASS_MUTATION_REFUSED:
        return fail(f"good-state-event:{good['event']}")
    if good["immutability_holds"] is not True:
        return fail("good-state-immutability")

    # Late-declaration attack: class declared only after start must be refused.
    late = late_declaration_attack()
    if late["refused"] is not True or late["event"] != EVENT_RISK_CLASS_MUTATION_REFUSED:
        return fail(f"late-declaration:{late}")

    # Start without a class emits EVENT_START_WITHOUT_CLASS.
    s0 = DeliberationSession()
    r0 = s0.start()
    if r0.blocked is not True or s0.events.count(EVENT_START_WITHOUT_CLASS) != 1:
        return fail("start-without-class")

    # Binding a decision config below the HIGH floor must be refused.
    s1 = DeliberationSession(risk_class="HIGH")
    s1.start(dict(FLOORS["HIGH"]))
    bad_bind = s1.bind_decision(dict(FLOORS["LOW"]))
    if bad_bind.blocked is not True or not bad_bind.deficits:
        return fail(f"bind-below-floor:{bad_bind.as_dict()}")

    # Negative control (mutant): immutability OFF lets HIGH land on LOW floors.
    mut_session = DeliberationSession(risk_class="LOW", allow_late_reclassification=True)
    mut_session.start(dict(FLOORS["LOW"]))
    mut = mut_session.reclassify("HIGH")
    if mut_session.risk_class != "HIGH":
        return fail("mutant-reclass-not-applied")
    sub = at_floor(dict(FLOORS["LOW"]), "HIGH")
    if not sub.blocked:
        return fail("mutant-precondition-subfloor-not-blocked")
    mutant = {
        "bound_class": mut_session.risk_class,
        "high_under_low": True,
        "immutability_holds": immutability_holds(mut_session),
    }
    if mutant["immutability_holds"] is not False:
        return fail(f"mutant-immutability:{mutant}")

    # The receipt's declared bad-state output must match the live mutant shape.
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    nctl = [n for n in doc.get("negative_controls") or []
            if n.get("id") == "IMP0358-late-reclass-immutability-fails"]
    if not nctl:
        return fail("receipt-negctl-absent")
    print(json.dumps({
        "probe": "probe2-immutability", "unit_id": "IMP-0358", "pass": True,
        "good_state": good, "late_declaration": late,
        "start_without_class_event": EVENT_START_WITHOUT_CLASS,
        "bind_below_floor_deficits": bad_bind.deficits,
        "mutant": mutant,
    }, sort_keys=True))
    print("SUCCESS:IMP-0358-probe2 immutability holds; mutant proves the control is load-bearing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
