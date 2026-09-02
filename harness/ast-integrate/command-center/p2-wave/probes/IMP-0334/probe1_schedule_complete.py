#!/usr/bin/env python3
"""Probe 1: rotation schedule completeness (every lens covered).

Also fail-closed: one participant cannot compile; a truncated schedule
is not accepted as complete. Live faithful run must cover every lens
in recorded turns.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from scenario import (  # noqa: E402
    ARTIFACT,
    LENS_IDS,
    PARTICIPANTS,
    QUESTION,
    SENTINEL,
)
from tools.council.protocol.hats import (  # noqa: E402
    HatsError,
    LensFaithfulSpeaker,
    REASON_SINGLE_SEAT,
    HatsEngine,
    audit_schedule,
    compile_schedule,
    plugin_record,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0334-probe1 {msg}")
    return 1


def main() -> int:
    schedule = compile_schedule(PARTICIPANTS, mode="parallel")
    audit = audit_schedule(schedule)
    staggered = compile_schedule(PARTICIPANTS, mode="staggered")
    staggered_audit = audit_schedule(staggered)
    truncated = audit_schedule(schedule.restrict_rounds(3))

    single_raised = False
    single_reason = ""
    try:
        compile_schedule(("solo",), mode="parallel")
    except HatsError as exc:
        single_raised = True
        single_reason = str(exc)

    engine = HatsEngine(mode="parallel")
    faithful = engine.run(PARTICIPANTS, QUESTION, LensFaithfulSpeaker())
    recorded_lenses = sorted({r.binding.lens_id for r in faithful.records})
    plugin = plugin_record()

    payload = {
        "probe": "probe1-schedule-complete",
        "unit_id": "IMP-0334",
        "audit": audit.to_dict(),
        "staggered_complete": staggered_audit.complete,
        "truncated_complete": truncated.complete,
        "truncated_missing": list(truncated.missing_lenses),
        "single_raised": single_raised,
        "single_reason": single_reason,
        "faithful_compliant": faithful.compliant,
        "faithful_lenses": recorded_lenses,
        "plugin_writes_output": plugin.get("writes_participant_output"),
        "n_bindings": audit.n_bindings,
        "pass": False,
    }
    ok = (
        audit.complete
        and audit.every_lens_covered
        and audit.every_participant_wore_every_lens
        and audit.each_lens_applied_by_multiple_participants
        and list(audit.lenses_covered) == sorted(LENS_IDS)
        and staggered_audit.complete
        and truncated.complete is False
        and len(truncated.missing_lenses) >= 1
        and single_raised
        and single_reason == REASON_SINGLE_SEAT
        and faithful.compliant
        and recorded_lenses == sorted(LENS_IDS)
        and plugin.get("writes_participant_output") is False
        and audit.n_bindings == len(PARTICIPANTS) * len(LENS_IDS)
    )
    payload["pass"] = bool(ok)
    print(json.dumps(payload, sort_keys=True))

    if not audit.complete:
        return fail("full parallel schedule not complete")
    if not audit.every_lens_covered:
        return fail("every_lens_covered false")
    if list(audit.lenses_covered) != sorted(LENS_IDS):
        return fail(f"lenses_covered={audit.lenses_covered}")
    if not audit.each_lens_applied_by_multiple_participants:
        return fail("a lens was applied by fewer than two participants")
    if not audit.every_participant_wore_every_lens:
        return fail("a participant missed a lens")
    if not staggered_audit.complete:
        return fail("staggered schedule not complete")
    if truncated.complete:
        return fail("truncated schedule accepted as complete")
    if not truncated.missing_lenses:
        return fail("truncated schedule still lists every lens")
    if not single_raised or single_reason != REASON_SINGLE_SEAT:
        return fail(f"single-seat reason={single_reason!r}")
    if not faithful.compliant:
        return fail(f"faithful run not compliant reasons={list(faithful.reasons)}")
    if recorded_lenses != sorted(LENS_IDS):
        return fail(f"recorded lenses {recorded_lenses}")
    if plugin.get("writes_participant_output") is not False:
        return fail("plugin claims to write participant output")

    art = REPO / ARTIFACT
    if not art.is_file():
        return fail("receipt missing")
    text = art.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    test_ids = doc.get("test_ids") or []
    if "IMP-0334-T-schedule-complete" not in test_ids:
        return fail("receipt missing schedule-complete test id")
    recorded = (doc.get("schedule_audit") or {})
    if recorded.get("complete") is not True:
        return fail("receipt schedule_audit.complete is not true")
    if recorded.get("every_lens_covered") is not True:
        return fail("receipt every_lens_covered drift")

    print(
        "schedule_complete=True truncated_rejected=True "
        f"single_seat_closed=True lenses={recorded_lenses}"
    )
    print("SUCCESS:IMP-0334-probe1 rotation schedule completeness")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
