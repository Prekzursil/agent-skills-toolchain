#!/usr/bin/env python3
"""Probe 2: independent reviewer. Re-derive ordering from the event log alone.

Does not read filesystem mtimes or git commit times. A world whose mtimes are
healthy but whose event log is back-dated must still fire.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import audit as A  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0167.json"
UNIT = "CNF-0167"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0167-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 2048:
        return fail("artifact missing or undersized")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:CNF-0167" not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    # Event-log only: pass events, never artifacts/mtimes/git.
    back_events = A.load_world("backdated")["events"]
    dep_events = A.load_world("dep-order")["events"]
    healthy_events = A.load_world("healthy")["events"]
    tz_events = A.load_world("timezone")["events"]

    back = A.audit_event_log(back_events)
    dep = A.audit_event_log(dep_events)
    healthy = A.audit_event_log(healthy_events)
    tz = A.audit_event_log(tz_events)

    if back.get("signals") != ["event-log"]:
        return fail(f"signals={back.get('signals')} want [event-log]")

    back_kinds = {i["kind"] for i in back["inversions"]}
    dep_kinds = {i["kind"] for i in dep["inversions"]}
    tz_order = [i for i in tz["inversions"] if i.get("kind") == "event-log-order-inversion"]

    print(
        json.dumps(
            {
                "probe": "probe2-eventlog-ordering",
                "unit_id": UNIT,
                "signals": back["signals"],
                "backdated_kinds": sorted(back_kinds),
                "dep_kinds": sorted(dep_kinds),
                "healthy_n": len(healthy["inversions"]),
                "timezone_order_n": len(tz_order),
                "timezone_equivalences": len(tz["equivalences"]),
            },
            sort_keys=True,
        )
    )

    if "receipt-before-cited-artifact" not in back_kinds:
        return fail("event-log-only missed planted back-dated receipt")
    if "receipt-before-dependency" not in dep_kinds:
        return fail("event-log-only missed dependency inversion")
    if healthy["inversions"]:
        return fail("event-log-only flagged healthy log")
    if tz_order:
        return fail("event-log-only flagged timezone same-instant pair")
    if not tz["equivalences"]:
        return fail("event-log-only did not record timezone equivalence")

    # Independence from mtimes: events inverted, synthetic mtimes would look healthy.
    # audit_event_log accepts no mtime channel, so a mtime-only mutant cannot pass
    # unless it ignores the inverted events. Confirm the function result changes
    # when the event timestamps are repaired.
    repaired = json.loads(json.dumps(back_events))
    for ev in repaired:
        if ev.get("kind") == "receipt-written":
            ev["ts"] = "2026-06-01T12:01:00Z"
    repaired_result = A.audit_event_log(repaired)
    repaired_kinds = {i["kind"] for i in repaired_result["inversions"]}
    if "receipt-before-cited-artifact" in repaired_kinds:
        return fail("repaired event log still flags receipt-before-cited-artifact")
    if len(repaired_result["inversions"]) == len(back["inversions"]):
        # event-log-order-inversion may also clear; counts must drop
        return fail("repairing event timestamps did not drop inversion count")

    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True or rev.get("verdict") != "PASS":
        return fail("artifact reviewer not independent PASS")
    art_rev = doc.get("reviewer_eventlog_only") or {}
    if art_rev.get("backdated_caught") is not True or art_rev.get("dep_caught") is not True:
        return fail("artifact reviewer_eventlog_only flags false")
    if art_rev.get("healthy_zero") is not True or art_rev.get("timezone_silent") is not True:
        return fail("artifact reviewer_eventlog_only healthy/timezone mismatch")
    if art_rev.get("signals") != ["event-log"]:
        return fail("artifact reviewer signals are not event-log-only")

    print("SUCCESS:CNF-0167-probe2 event-log-only ordering re-derived")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
