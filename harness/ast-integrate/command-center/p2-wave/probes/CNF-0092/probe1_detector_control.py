#!/usr/bin/env python3
"""Probe 1: re-run the detector control on known-broken and contested fixtures.

A reviewer who only re-reads CNF-0092-instant-unanimity-trigger.json has
verified nothing. This probe executes the live runner and then checks that
the artifact recorded the same fire/silent pair.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import payload as P  # noqa: E402
import runtime as R  # noqa: E402
import unanimity as U  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0092-instant-unanimity-trigger.json"
SENTINEL_NEEDLE = (
    "the trigger fired on the unanimity fixture and stayed silent on the "
    "contested control"
)


def fail(why: str) -> int:
    print(f"FAILED:CNF-0092-probe1 {why}")
    return 1


def main() -> int:
    live = R.run_all()
    compact = R.compact(live)
    print(json.dumps(compact, sort_keys=True))
    if not live["instant_fired"]:
        return fail("groupthink-undetected: instant fixture did not fire")
    if not live["contested_silent"]:
        return fail("trigger-overfires: contested fixture fired")
    if not live["trigger_recorded_in_audit_log"]:
        return fail("audit-gap: INSTANT_UNANIMITY_TRIGGER missing from live log")
    events = [e.get("event") for e in live["instant"]["audit_events"]]
    if U.EVENT_TRIGGER not in events:
        return fail("audit-gap: trigger event name absent")
    if U.EVENT_ROUND_ONE_VOTE not in events:
        return fail("audit-gap: round-one vote record absent")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL_NEEDLE not in text or "SUCCESS:CNF-0092" not in text:
        return fail("sentinel-absent")

    by = {r["fixture_id"]: r for r in P.runs_of(doc)}
    inst = by.get("instant-unanimity-clones") or {}
    cont = by.get("contested-split") or {}
    if inst.get("trigger_fired") is not True:
        return fail("artifact did not record instant fire")
    if cont.get("trigger_fired") is not False:
        return fail("artifact did not record contested silent")
    if inst.get("round_one_votes") != live["instant"]["round_one_votes"]:
        return fail("round-one vote record drifted from live run")
    art_events = [e.get("event") for e in (inst.get("audit_events") or [])]
    if U.EVENT_TRIGGER not in art_events:
        return fail("artifact audit log missing trigger event")

    print("SUCCESS:CNF-0092-probe1 detector-control fire-on-broken silent-on-contested")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
