#!/usr/bin/env python3
"""Probe 1: primed council transcript + which trigger fired + transcript change.

Mechanically: live CNL-0080 evaluate_fixture on the primed fixture and the
late-unanimity control. Does not compare overlay-off decisions (probe 2).
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
    print(f"FAILED:ADV-0091-probe1 {msg}")
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
    print(
        json.dumps(
            {
                "probe": "probe1-primed-transcript",
                "trigger_fired": primed["live"]["instant_unanimity_trigger"],
                "which": primed["live"]["executed_intervention"],
                "outcome_kind": primed["live"]["outcome_kind"],
                "transcript_n": len(primed["transcript"]),
                "independent_briefs": primed["independent_briefs"],
                "late_silent": facts["late_silent"],
                "listed_any": facts["primed_listed_interventions_any"],
                "delta": primed["delta"],
            },
            sort_keys=True,
        )
    )
    if not facts["primed_trigger"]:
        return fail("primed council did not fire instant_unanimity_trigger")
    if primed["live"]["executed_intervention"] != "hold_for_revaluation":
        return fail("primed intervention is not hold_for_revaluation")
    if primed["live"]["outcome_kind"] != "AGREEMENT_HELD_FOR_REVALUATION":
        return fail(f"primed kind {primed['live']['outcome_kind']}")
    if facts["primed_listed_interventions_any"]:
        return fail("listed interventions claimed without engine support")
    if not facts["late_silent"]:
        return fail("late legitimate unanimity also fired the trigger")
    if not facts["contested_silent"]:
        return fail("contested fixture fired instant-unanimity trigger")
    if not facts["timer_silent"]:
        return fail("timer exhaustion fired instant-unanimity trigger")
    if primed["independent_briefs"] != 0:
        return fail("primed fixture is not zero-brief")
    if any(row.get("independent_brief") for row in primed["transcript"]):
        return fail("primed transcript contains independent briefs")

    art_trigger = ((doc.get("primed_run") or {}).get("live") or {}).get(
        "instant_unanimity_trigger"
    )
    if art_trigger is not True:
        return fail("artifact primed trigger is not True")
    print(
        "SUCCESS:ADV-0091-probe1 primed trigger=hold_for_revaluation "
        "late-control silent listed-interventions absent"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
