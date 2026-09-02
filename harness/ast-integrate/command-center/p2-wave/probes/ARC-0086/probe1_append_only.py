#!/usr/bin/env python3
"""Named probe 1: modify one historical line; the integrity check detects it.

Both-states: unmodified log verifies; after an in-place payload edit the chain
breaks at that record. Line count is unchanged so a count-only check would miss
it. Isolated tempfile only; never live EVENTS.jsonl.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import eventlog as E  # noqa: E402

ART = REPO / "command-center/phase4/contracts/ARC-0086.json"
LIVE = REPO / "command-center/events/EVENTS.jsonl"


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0086-probe1 {msg}")
    return 1


def seed(path: Path) -> list[dict]:
    rows = []
    rows.append(
        E.append_record(
            path,
            actor="probe1",
            unit_id="ARC-0086",
            phase="4",
            from_state="OPEN",
            to_state="IN-PROGRESS",
            correlation_id="arc-0086-probe1",
            writer_id="probe1-w",
            payload={"note": "first", "n": 1},
            ts="2026-08-24T20:00:00Z",
        )
    )
    rows.append(
        E.append_record(
            path,
            actor="probe1",
            unit_id="ARC-0086",
            phase="4",
            from_state="IN-PROGRESS",
            to_state="IN-PROGRESS",
            correlation_id="arc-0086-probe1",
            writer_id="probe1-w",
            payload={"note": "second", "n": 2},
            ts="2026-08-24T20:00:01Z",
        )
    )
    rows.append(
        E.append_record(
            path,
            actor="probe1",
            unit_id="ARC-0086",
            phase="4",
            from_state="IN-PROGRESS",
            to_state="SUCCESS",
            correlation_id="arc-0086-probe1",
            writer_id="probe1-w",
            payload={"note": "third", "n": 3},
            ts="2026-08-24T20:00:02Z",
        )
    )
    return rows


def main() -> int:
    if LIVE.is_file() and LIVE.stat().st_size > 0:
        before_live = LIVE.read_bytes()
    else:
        before_live = None
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("contract artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    blob = json.dumps(doc)
    if doc.get("unit_id") != "ARC-0086":
        return fail(f"unit_id {doc.get('unit_id')!r}")
    if "SUCCESS:ARC-0086" not in blob:
        return fail("sentinel absent")
    enf = doc.get("append_only_enforcement") or {}
    if enf.get("id") != E.ENFORCEMENT_ID:
        return fail(f"enforcement id {enf.get('id')!r}")
    if enf.get("in_place_edit_detectable_by") != "hash-chain":
        return fail("contract does not name hash-chain detection")
    if enf.get("line_count_is_not_integrity") is not True:
        return fail("contract missing line_count_is_not_integrity")

    with tempfile.TemporaryDirectory(prefix="arc0086-p1-") as tmp:
        path = Path(tmp) / "EVENTS.jsonl"
        seeded = seed(path)
        if path.resolve() == LIVE.resolve():
            return fail("wrote to live EVENTS.jsonl")
        original = path.read_bytes()
        before = E.verify_chain(E.load_records(path))
        if not before["ok"] or before["record_count"] != 3:
            return fail(f"unmodified chain not ok: {before}")
        line_count_before = original.count(b"\n")
        E.tamper_line(path, 1, "payload.note", "MUTATED-HISTORICAL")
        tampered = path.read_bytes()
        line_count_after = tampered.count(b"\n")
        after = E.verify_chain(E.load_records(path))
        if after["ok"]:
            return fail("in-place edit was not detected")
        if after["broken_at"] != 1:
            return fail(f"broken_at={after['broken_at']!r} want 1")
        if after["broken_event_id"] != seeded[1]["event_id"]:
            return fail(f"broken_event_id={after['broken_event_id']!r}")
        if line_count_before != line_count_after:
            return fail("line count changed; this is not an in-place edit control")
        if original == tampered:
            return fail("tamper did not change bytes")
        restored = Path(tmp) / "EVENTS.restored.jsonl"
        restored.write_bytes(original)
        restored_v = E.verify_chain(E.load_records(restored))
        if not restored_v["ok"]:
            return fail("restored original no longer verifies")

    if before_live is None:
        if LIVE.is_file() and LIVE.stat().st_size > 0:
            return fail("created live EVENTS.jsonl")
    elif LIVE.read_bytes() != before_live:
        return fail("mutated live EVENTS.jsonl")

    summary = {
        "probe": "probe1-append-only",
        "unit_id": "ARC-0086",
        "pass": True,
        "unmodified_ok": True,
        "tampered_ok": False,
        "broken_at": 1,
        "broken_event_id": seeded[1]["event_id"],
        "line_count_unchanged": True,
        "both_states": True,
        "wrote_to_live_events": False,
        "enforcement": E.ENFORCEMENT_ID,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"unmodified_ok=True tampered_ok=False broken_at=1 "
        f"line_count_unchanged=True"
    )
    print("SUCCESS:ARC-0086-probe1 append-only control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
