#!/usr/bin/env python3
"""Probe 1: pause / inject / resume lifecycle and owner-origin distinguishability.

A live council records two participant turns, the owner pauses, injects
guidance and a constraint, then resumes. A further participant turn is
accepted only after resume. The final artifact must mark every intervention
with origin=owner and origin_marker owner-origin:<id>, and those markers
must not appear on participant turns.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.owner import (  # noqa: E402
    KIND_CONSTRAINT,
    KIND_GUIDANCE,
    KIND_PAUSE,
    KIND_RESUME,
    KIND_TURN,
    ORIGIN_OWNER,
    ORIGIN_PARTICIPANT,
    OWNER_MARKER_PREFIX,
    OwnerChannelError,
    LiveCouncil,
    prefix_hash,
    run_lifecycle_demo,
)

UNIT = "IMP-0342"
ART = REPO / "command-center/receipts/IMP-0342.json"


def _check_receipt() -> str | None:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return "receipt missing"
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return f"receipt unparseable {exc}"
    if not isinstance(doc, dict):
        return "receipt not object"
    if str(doc.get("unit_id")) != UNIT:
        return f"unit_id {doc.get('unit_id')}"
    if "SUCCESS:IMP-0342" not in text:
        return "sentinel absent"
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return f"self-declared {doc.get('state')}"
    return None


def main() -> int:
    rec_err = _check_receipt()
    if rec_err:
        print(f"FAILED:IMP-0342-probe1 {rec_err}")
        return 1

    demo = run_lifecycle_demo()
    art = demo["artifact"]
    scan = demo["scan"]
    print(
        json.dumps(
            {
                "status_after": demo["status_after"],
                "event_count": demo["event_count"],
                "prefix_of_prior_unchanged": demo["prefix_of_prior_unchanged"],
                "prior_texts_unchanged": demo["prior_texts_unchanged"],
                "distinguishable": scan["distinguishable"],
                "every_intervention_has_owner_marker": scan[
                    "every_intervention_has_owner_marker"
                ],
                "intervention_kinds": scan["intervention_kinds"],
                "intervention_markers": scan["intervention_markers"],
            },
            sort_keys=True,
        )
    )

    if demo["status_after"] != "running":
        print(f"FAILED:IMP-0342-probe1 status={demo['status_after']}")
        return 1
    if not demo["prefix_of_prior_unchanged"] or not demo["prior_texts_unchanged"]:
        print("FAILED:IMP-0342-probe1 intervention rewrote a prior position")
        return 1
    if not scan["distinguishable"] or not scan["every_intervention_has_owner_marker"]:
        print("FAILED:IMP-0342-probe1 owner interventions not distinguishable")
        return 1
    expected_kinds = [KIND_PAUSE, KIND_GUIDANCE, KIND_CONSTRAINT, KIND_RESUME]
    if scan["intervention_kinds"] != expected_kinds:
        print(f"FAILED:IMP-0342-probe1 kinds {scan['intervention_kinds']}")
        return 1
    if not all(
        str(m).startswith(OWNER_MARKER_PREFIX) for m in scan["intervention_markers"]
    ):
        print("FAILED:IMP-0342-probe1 origin marker prefix missing")
        return 1

    for event in art["interventions"]:
        if event.get("origin") != ORIGIN_OWNER:
            print(f"FAILED:IMP-0342-probe1 intervention origin {event.get('origin')}")
            return 1
    for event in art["contributions"]:
        if event.get("origin") != ORIGIN_PARTICIPANT:
            print(f"FAILED:IMP-0342-probe1 contribution origin {event.get('origin')}")
            return 1
        if event.get("kind") != KIND_TURN:
            print(f"FAILED:IMP-0342-probe1 contribution kind {event.get('kind')}")
            return 1

    council = LiveCouncil("council-imp-0342-guard", owner_id="owner-1")
    council.start(["alice"], seed="guard")
    council.record_turn("alice", "a position")
    try:
        council.inject_guidance("owner-1", "should be refused while running")
        print("FAILED:IMP-0342-probe1 inject-while-running did not refuse")
        return 1
    except OwnerChannelError as exc:
        print(f"inject_while_running_refused={type(exc).__name__}")
    council.pause("owner-1", "hold")
    try:
        council.record_turn("alice", "should be refused while paused")
        print("FAILED:IMP-0342-probe1 turn-while-paused did not refuse")
        return 1
    except OwnerChannelError as exc:
        print(f"turn_while_paused_refused={type(exc).__name__}")
    try:
        council.pause("owner-1", "double pause")
        print("FAILED:IMP-0342-probe1 double-pause did not refuse")
        return 1
    except OwnerChannelError as exc:
        print(f"double_pause_refused={type(exc).__name__}")
    council.inject_guidance("owner-1", "ok while paused")
    council.resume("owner-1")
    council.record_turn("alice", "after resume")
    events = council.log.events()
    print(f"guard_event_count={len(events)} prefix={prefix_hash(events, 2)[:16]}")

    print("SUCCESS:IMP-0342-probe1 pause-inject-resume lifecycle and origin markers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
