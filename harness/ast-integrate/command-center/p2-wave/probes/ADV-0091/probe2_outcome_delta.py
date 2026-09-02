#!/usr/bin/env python3
"""Probe 2: final-decision comparison, trigger on vs trigger disabled.

Mechanically different from probe 1: parser-free overlay_off vs live
evaluate_fixture. Does not inspect transcript lines. A trigger that fires
but leaves outcome_kind identical is ceremonial.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import constants as C  # noqa: E402
import harness as H  # noqa: E402

ART = C.REPO / C.OUT_REL
SENTINEL = C.completion_sentinel()
BLOCKED = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0091-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable {exc}")
    if str(doc.get("state") or "").upper() in BLOCKED:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel-absent")

    matrix = H.run_matrix()
    facts = matrix["facts"]
    primed = matrix["primed"]
    late = matrix["late_legitimate"]
    print(
        json.dumps(
            {
                "probe": "probe2-outcome-delta",
                "primed_live_kind": primed["live"]["outcome_kind"],
                "primed_off_kind": primed["overlay_off"]["outcome_kind"],
                "primed_changed": facts["primed_outcome_changed"],
                "late_live_kind": late["live"]["outcome_kind"],
                "late_off_kind": late["overlay_off"]["outcome_kind"],
                "late_changed": late["outcome_changed_vs_disabled"],
                "ceremonial": (
                    primed["live"]["instant_unanimity_trigger"] is True
                    and not facts["primed_outcome_changed"]
                ),
            },
            sort_keys=True,
        )
    )
    if primed["live"]["outcome_kind"] != "AGREEMENT_HELD_FOR_REVALUATION":
        return fail("live primed outcome is not held for revaluation")
    if primed["overlay_off"]["outcome_kind"] != "AGREEMENT":
        return fail("overlay-off primed outcome is not AGREEMENT")
    if not facts["primed_outcome_changed"]:
        return fail("trigger is ceremonial: outcome identical with overlay off")
    if late["live"]["outcome_kind"] != "AGREEMENT":
        return fail("late legitimate live outcome is not AGREEMENT")
    if late["outcome_changed_vs_disabled"]:
        return fail("late legitimate overlay changed the decision")
    if not facts["late_kind_agreement"]:
        return fail("late legitimate is not AGREEMENT")

    delta = doc.get("outcome_delta") or {}
    if delta.get("primed_changed") is not True:
        return fail("artifact outcome_delta.primed_changed is not True")
    if delta.get("late_changed") is not False:
        return fail("artifact outcome_delta.late_changed is not False")
    print(
        "SUCCESS:ADV-0091-probe2 primed HOLD vs overlay-off AGREEMENT; "
        "late control unchanged"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
